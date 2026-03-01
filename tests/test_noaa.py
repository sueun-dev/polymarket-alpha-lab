"""Tests for data.noaa -- NOAA Weather data provider."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from unittest import mock

import pytest

from data.noaa import NOAAWeatherProvider


# ---------------------------------------------------------------------------
# Helpers -- realistic mock API responses
# ---------------------------------------------------------------------------

def _make_points_response(
    office: str = "OKX",
    grid_x: int = 33,
    grid_y: int = 37,
) -> Dict[str, Any]:
    """Return a realistic /points/{lat},{lon} response."""
    return {
        "properties": {
            "gridId": office,
            "gridX": grid_x,
            "gridY": grid_y,
            "forecast": f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast",
            "forecastHourly": f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly",
        },
    }


def _make_period(
    temperature: int = 72,
    temperature_unit: str = "F",
    short_forecast: str = "Partly Cloudy",
    start_time: str = "2026-02-28T14:00:00-05:00",
    is_daytime: bool = True,
    precip_value: Any = 20,
) -> Dict[str, Any]:
    """Build a single hourly forecast period dict."""
    pop: Any = {"unitCode": "wmoUnit:percent", "value": precip_value}
    return {
        "temperature": temperature,
        "temperatureUnit": temperature_unit,
        "shortForecast": short_forecast,
        "startTime": start_time,
        "isDaytime": is_daytime,
        "probabilityOfPrecipitation": pop,
    }


def _make_forecast_response(periods: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """Return a realistic hourly forecast response."""
    if periods is None:
        periods = [_make_period(temperature=70 + i, precip_value=10 * i) for i in range(6)]
    return {"properties": {"periods": periods}}


# ---------------------------------------------------------------------------
# extract_city_from_question
# ---------------------------------------------------------------------------


class TestExtractCityFromQuestion:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    def test_new_york_in_question(self) -> None:
        result = self.provider.extract_city_from_question(
            "Will temperature in New York exceed 90\u00b0F?"
        )
        assert result == "new york"

    def test_chicago_in_question(self) -> None:
        result = self.provider.extract_city_from_question(
            "Will it rain in Chicago tomorrow?"
        )
        assert result == "chicago"

    def test_no_city_returns_none(self) -> None:
        result = self.provider.extract_city_from_question(
            "Will Bitcoin reach $100k?"
        )
        assert result is None

    def test_los_angeles_in_question(self) -> None:
        result = self.provider.extract_city_from_question(
            "Los Angeles weather alert"
        )
        assert result == "los angeles"

    def test_case_insensitive(self) -> None:
        result = self.provider.extract_city_from_question(
            "SEATTLE RAIN FORECAST"
        )
        assert result == "seattle"

    def test_san_francisco_matched_before_sf(self) -> None:
        # "san francisco" is longer than "sf", so it should match first.
        result = self.provider.extract_city_from_question(
            "Will San Francisco see snow?"
        )
        assert result == "san francisco"

    def test_sf_shorthand(self) -> None:
        result = self.provider.extract_city_from_question(
            "Will it be sunny in SF this weekend?"
        )
        assert result == "sf"

    def test_washington_dc(self) -> None:
        result = self.provider.extract_city_from_question(
            "Will Washington DC get a heatwave?"
        )
        assert result == "washington dc"

    def test_las_vegas(self) -> None:
        result = self.provider.extract_city_from_question(
            "Record heat in Las Vegas this summer?"
        )
        assert result == "las vegas"

    def test_denver(self) -> None:
        result = self.provider.extract_city_from_question(
            "Snow expected in Denver?"
        )
        assert result == "denver"

    def test_empty_question(self) -> None:
        assert self.provider.extract_city_from_question("") is None


# ---------------------------------------------------------------------------
# get_grid_info
# ---------------------------------------------------------------------------


class TestGetGridInfo:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_success(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = _make_points_response("OKX", 33, 37)
        result = self.provider.get_grid_info(40.7128, -74.0060)
        assert result == {"office": "OKX", "gridX": 33, "gridY": 37}
        mock_http.assert_called_once_with("https://api.weather.gov/points/40.7128,-74.006")

    @mock.patch("data.noaa.http_get_json")
    def test_http_failure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = RuntimeError("request failed")
        result = self.provider.get_grid_info(40.7128, -74.0060)
        assert result is None

    @mock.patch("data.noaa.http_get_json")
    def test_bad_response_structure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"unexpected": "data"}
        result = self.provider.get_grid_info(40.7128, -74.0060)
        assert result is None

    @mock.patch("data.noaa.http_get_json")
    def test_caching(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = _make_points_response("OKX", 33, 37)
        # First call -- hits HTTP.
        r1 = self.provider.get_grid_info(40.7128, -74.0060)
        # Second call -- served from cache.
        r2 = self.provider.get_grid_info(40.7128, -74.0060)
        assert r1 == r2
        assert mock_http.call_count == 1

    @mock.patch("data.noaa.http_get_json")
    def test_none_response_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = None
        result = self.provider.get_grid_info(40.7128, -74.0060)
        assert result is None


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


class TestGetForecast:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_success(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=75)]
        mock_http.side_effect = [
            _make_points_response("OKX", 33, 37),
            _make_forecast_response(periods),
        ]
        result = self.provider.get_forecast("new york")
        assert result is not None
        assert len(result) == 1
        assert result[0]["temperature"] == 75

    @mock.patch("data.noaa.http_get_json")
    def test_unknown_city_returns_none(self, mock_http: mock.MagicMock) -> None:
        result = self.provider.get_forecast("atlantis")
        assert result is None
        mock_http.assert_not_called()

    @mock.patch("data.noaa.http_get_json")
    def test_grid_failure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = RuntimeError("request failed")
        result = self.provider.get_forecast("chicago")
        assert result is None

    @mock.patch("data.noaa.http_get_json")
    def test_forecast_http_failure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = [
            _make_points_response("LOT", 76, 73),
            RuntimeError("request failed"),
        ]
        result = self.provider.get_forecast("chicago")
        assert result is None

    @mock.patch("data.noaa.http_get_json")
    def test_bad_forecast_structure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = [
            _make_points_response("LOT", 76, 73),
            {"unexpected": "data"},
        ]
        result = self.provider.get_forecast("chicago")
        assert result is None

    @mock.patch("data.noaa.http_get_json")
    def test_caching(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=80)]
        mock_http.side_effect = [
            _make_points_response("OKX", 33, 37),
            _make_forecast_response(periods),
        ]
        r1 = self.provider.get_forecast("new york")
        # Second call should be served entirely from cache (no additional HTTP).
        r2 = self.provider.get_forecast("new york")
        assert r1 == r2
        # One call for points, one for forecast -- no more.
        assert mock_http.call_count == 2

    @mock.patch("data.noaa.http_get_json")
    def test_case_insensitive_city(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=85)]
        mock_http.side_effect = [
            _make_points_response("MFL", 76, 53),
            _make_forecast_response(periods),
        ]
        result = self.provider.get_forecast("  Miami  ")
        assert result is not None
        assert result[0]["temperature"] == 85


# ---------------------------------------------------------------------------
# fetch (main entry point)
# ---------------------------------------------------------------------------


class TestFetch:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_delegates_to_get_forecast(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period()]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        result = self.provider.fetch(city="new york")
        assert result is not None
        assert isinstance(result, list)

    def test_no_city_returns_none(self) -> None:
        assert self.provider.fetch() is None

    def test_empty_city_returns_none(self) -> None:
        assert self.provider.fetch(city="") is None


# ---------------------------------------------------------------------------
# temperature_probability
# ---------------------------------------------------------------------------


class TestTemperatureProbability:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_above_threshold(self, mock_http: mock.MagicMock) -> None:
        # Temperatures: 60, 70, 80, 90, 100
        periods = [_make_period(temperature=t) for t in [60, 70, 80, 90, 100]]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=75, above=True, hours=5)
        # 80, 90, 100 are above 75 -> 3/5 = 0.6
        assert prob == pytest.approx(0.6)

    @mock.patch("data.noaa.http_get_json")
    def test_below_threshold(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=t) for t in [60, 70, 80, 90, 100]]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=75, above=False, hours=5)
        # 60, 70 are below 75 -> 2/5 = 0.4
        assert prob == pytest.approx(0.4)

    @mock.patch("data.noaa.http_get_json")
    def test_hours_limits_periods(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=t) for t in [60, 70, 80, 90, 100]]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=75, above=True, hours=3)
        # Only first 3: 60, 70, 80.  Only 80 > 75 -> 1/3
        assert prob == pytest.approx(1 / 3)

    @mock.patch("data.noaa.http_get_json")
    def test_all_above(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=100) for _ in range(4)]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=50, above=True, hours=4)
        assert prob == pytest.approx(1.0)

    @mock.patch("data.noaa.http_get_json")
    def test_none_above(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=30) for _ in range(4)]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=50, above=True, hours=4)
        assert prob == pytest.approx(0.0)

    def test_unknown_city_returns_none(self) -> None:
        prob = self.provider.temperature_probability("atlantis", threshold_f=80)
        assert prob is None

    @mock.patch("data.noaa.http_get_json")
    def test_http_failure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = RuntimeError("request failed")
        prob = self.provider.temperature_probability("miami", threshold_f=90)
        assert prob is None

    @mock.patch("data.noaa.http_get_json")
    def test_threshold_equality_not_counted(self, mock_http: mock.MagicMock) -> None:
        # Temperature exactly at threshold should NOT be counted (strictly above/below).
        periods = [_make_period(temperature=75)]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=75, above=True, hours=1)
        assert prob == pytest.approx(0.0)

    @mock.patch("data.noaa.http_get_json")
    def test_threshold_equality_below_not_counted(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(temperature=75)]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=75, above=False, hours=1)
        assert prob == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# precipitation_probability
# ---------------------------------------------------------------------------


class TestPrecipitationProbability:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_average_precip(self, mock_http: mock.MagicMock) -> None:
        # precip values: 0, 20, 40, 60
        periods = [_make_period(precip_value=v) for v in [0, 20, 40, 60]]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.precipitation_probability("new york", hours=4)
        # average = (0 + 20 + 40 + 60) / (4 * 100) = 120 / 400 = 0.3
        assert prob == pytest.approx(0.3)

    @mock.patch("data.noaa.http_get_json")
    def test_null_precip_values_treated_as_zero(self, mock_http: mock.MagicMock) -> None:
        periods = [
            _make_period(precip_value=50),
            _make_period(precip_value=None),
            _make_period(precip_value=None),
            _make_period(precip_value=50),
        ]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.precipitation_probability("new york", hours=4)
        # (50 + 0 + 0 + 50) / (4 * 100) = 100 / 400 = 0.25
        assert prob == pytest.approx(0.25)

    @mock.patch("data.noaa.http_get_json")
    def test_all_100_percent(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(precip_value=100) for _ in range(3)]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.precipitation_probability("new york", hours=3)
        assert prob == pytest.approx(1.0)

    @mock.patch("data.noaa.http_get_json")
    def test_all_zero_percent(self, mock_http: mock.MagicMock) -> None:
        periods = [_make_period(precip_value=0) for _ in range(3)]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.precipitation_probability("new york", hours=3)
        assert prob == pytest.approx(0.0)

    @mock.patch("data.noaa.http_get_json")
    def test_hours_limits_periods(self, mock_http: mock.MagicMock) -> None:
        # 5 periods, but only ask for 2
        periods = [_make_period(precip_value=v) for v in [80, 40, 0, 0, 0]]
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response(periods),
        ]
        prob = self.provider.precipitation_probability("new york", hours=2)
        # (80 + 40) / (2 * 100) = 120 / 200 = 0.6
        assert prob == pytest.approx(0.6)

    def test_unknown_city_returns_none(self) -> None:
        prob = self.provider.precipitation_probability("atlantis")
        assert prob is None

    @mock.patch("data.noaa.http_get_json")
    def test_http_failure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = RuntimeError("request failed")
        prob = self.provider.precipitation_probability("boston")
        assert prob is None

    @mock.patch("data.noaa.http_get_json")
    def test_missing_precip_key_treated_as_zero(self, mock_http: mock.MagicMock) -> None:
        # Period without probabilityOfPrecipitation key entirely
        period_no_pop = {"temperature": 70, "temperatureUnit": "F", "shortForecast": "Clear"}
        period_with_pop = _make_period(precip_value=60)
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response([period_no_pop, period_with_pop]),
        ]
        prob = self.provider.precipitation_probability("new york", hours=2)
        # (0 + 60) / (2 * 100) = 0.3
        assert prob == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Caching behaviour (cross-method)
# ---------------------------------------------------------------------------


class TestCachingBehaviour:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_grid_cache_shared_across_forecast_calls(self, mock_http: mock.MagicMock) -> None:
        """Two forecast calls for the same city should reuse the grid cache."""
        periods_1 = [_make_period(temperature=65)]
        periods_2 = [_make_period(temperature=78)]
        mock_http.side_effect = [
            _make_points_response("OKX", 33, 37),  # grid info (1st call)
            _make_forecast_response(periods_1),     # forecast (1st call)
            # Grid is cached, so only forecast is fetched for 2nd call:
            # But forecast is also cached, so no HTTP call needed!
        ]
        r1 = self.provider.get_forecast("new york")
        r2 = self.provider.get_forecast("new york")
        assert r1 == r2
        # Only 2 HTTP calls total (1 grid + 1 forecast).
        assert mock_http.call_count == 2

    @mock.patch("data.noaa.http_get_json")
    def test_forecast_cache_expiry(self, mock_http: mock.MagicMock) -> None:
        """After forecast cache expires, a new HTTP call is made for forecast but not grid."""
        periods_1 = [_make_period(temperature=65)]
        periods_2 = [_make_period(temperature=78)]
        mock_http.side_effect = [
            _make_points_response("OKX", 33, 37),
            _make_forecast_response(periods_1),
            # After cache expiry, only forecast is re-fetched (grid still valid):
            _make_forecast_response(periods_2),
        ]

        self.provider.get_forecast("new york")
        # Expire the forecast cache manually
        cache_key = "forecast:new york"
        self.provider._cache_ts[cache_key] = time.time() - 7200  # 2 hours ago

        r2 = self.provider.get_forecast("new york")
        assert r2 is not None
        assert r2[0]["temperature"] == 78
        # 3 calls: grid, forecast, forecast (re-fetched after expiry)
        assert mock_http.call_count == 3


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def setup_method(self) -> None:
        self.provider = NOAAWeatherProvider()

    @mock.patch("data.noaa.http_get_json")
    def test_grid_info_none_response_graceful(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = None
        assert self.provider.get_grid_info(0.0, 0.0) is None

    @mock.patch("data.noaa.http_get_json")
    def test_forecast_empty_periods_list(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response([]),
        ]
        result = self.provider.get_forecast("new york")
        assert result == []

    @mock.patch("data.noaa.http_get_json")
    def test_temperature_probability_empty_forecast(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response([]),
        ]
        prob = self.provider.temperature_probability("new york", threshold_f=80)
        # Empty list is falsy -> returns None
        assert prob is None

    @mock.patch("data.noaa.http_get_json")
    def test_precip_probability_empty_forecast(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = [
            _make_points_response(),
            _make_forecast_response([]),
        ]
        prob = self.provider.precipitation_probability("new york")
        # Empty list is falsy -> returns None
        assert prob is None

    def test_provider_name(self) -> None:
        p = NOAAWeatherProvider()
        assert p.name == "noaa_weather"

    def test_provider_logger_name(self) -> None:
        p = NOAAWeatherProvider()
        assert p.logger.name == "data.noaa_weather"
