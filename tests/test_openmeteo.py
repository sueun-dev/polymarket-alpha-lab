from __future__ import annotations

from unittest import mock

from data.openmeteo import OpenMeteoProvider


def _geo_response():
    return {
        "results": [
            {
                "name": "Seoul",
                "country_code": "KR",
                "latitude": 37.5665,
                "longitude": 126.9780,
            }
        ]
    }


def _forecast_response():
    return {
        "current": {
            "time": "2026-03-11T12:00",
            "temperature_2m": 8.0,
        },
        "hourly": {
            "time": ["2026-03-11T12:00", "2026-03-11T13:00"],
            "temperature_2m": [8.0, 9.0],
            "precipitation_probability": [20, 35],
            "precipitation": [0.0, 1.2],
            "snowfall": [0.0, 0.0],
        },
        "daily": {
            "time": ["2026-03-11", "2026-03-12"],
            "temperature_2m_max": [11.0, 12.0],
            "temperature_2m_min": [3.0, 5.0],
            "precipitation_sum": [1.2, 0.0],
            "snowfall_sum": [0.0, 0.0],
            "precipitation_probability_max": [35, 10],
        },
    }


@mock.patch("data.openmeteo.http_get_json")
def test_openmeteo_forecast_and_grid_data(mock_http: mock.MagicMock) -> None:
    mock_http.side_effect = [_geo_response(), _forecast_response()]
    provider = OpenMeteoProvider()

    periods = provider.get_forecast("seoul", country_code="kr")
    grid = provider.get_grid_data("seoul", country_code="kr")
    observation = provider.get_latest_observation("seoul", country_code="kr")

    assert periods is not None
    assert len(periods) == 2
    assert periods[0]["temperature"] == 8.0
    assert grid is not None
    assert len(grid["temperature"]["values"]) == 2
    assert len(grid["maxTemperature"]["values"]) == 2
    assert observation is not None
    assert observation["temperature_c"] == 8.0
    assert observation["temperature_f"] == 46.4


@mock.patch("data.openmeteo.http_get_json")
def test_openmeteo_city_profile_uses_geocode(mock_http: mock.MagicMock) -> None:
    mock_http.return_value = _geo_response()
    provider = OpenMeteoProvider()

    profile = provider.city_profile("seoul", country_code="kr")

    assert profile is not None
    assert profile["canonical"] == "seoul"
    assert profile["country_code"] == "kr"
    assert profile["forecast_source"] == "open_meteo"
