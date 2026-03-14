import pytest

from core.models import Market, Opportunity
from data import DataRegistry
from data.aviationweather import AviationWeatherProvider
from data.global_climate import GlobalClimateProvider
from data.noaa import NOAAWeatherProvider
from data.nws_climate import NWSClimateProvider
from strategies.tier_s.s02_weather_noaa import WeatherNOAA


def _forecast(temp: float, count: int = 24):
    return [
        {
            "temperature": temp,
            "temperatureUnit": "F",
            "startTime": "2026-03-11T08:00:00-05:00",
            "probabilityOfPrecipitation": {"value": 20},
        }
        for _ in range(count)
    ]


def _forecast_c(temp: float, count: int = 24):
    return [
        {
            "temperature": temp,
            "temperatureUnit": "C",
            "startTime": "2026-03-11T08:00:00-05:00",
            "probabilityOfPrecipitation": {"value": 20},
        }
        for _ in range(count)
    ]


def _grid():
    return {
        "temperature": {
            "values": [
                {"validTime": "2026-03-11T13:00:00+00:00/PT1H", "value": 2.0},
                {"validTime": "2026-03-11T14:00:00+00:00/PT1H", "value": 4.0},
            ]
        },
        "maxTemperature": {
            "values": [
                {"validTime": "2026-03-11T13:00:00+00:00/PT12H", "value": 5.0},
            ]
        },
        "probabilityOfPrecipitation": {
            "values": [
                {"validTime": "2026-03-11T13:00:00+00:00/PT1H", "value": 60},
            ]
        },
        "quantitativePrecipitation": {
            "values": [
                {"validTime": "2026-03-11T13:00:00+00:00/PT6H", "value": 4.0},
            ]
        },
        "snowfallAmount": {
            "values": [
                {"validTime": "2026-03-11T13:00:00+00:00/PT6H", "value": 0.0},
            ]
        },
    }


def _global_series():
    provider = GlobalClimateProvider()
    return provider.parse_nasa_monthly_series(
        """
        GLOBAL Land-Ocean Temperature Index in 0.01 degrees Celsius   base period: 1951-1980
Year   Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec    J-D D-N    DJF  MAM  JJA  SON  Year
2022    92   95   98   94   90   89   93  101   97  104  102   98     96  96     95   94   94  101  2022
2023   101  110  112  109  103  101  107  114  111  116  115  112    110 110    103  108  107  114  2023
2024   125  143  139  131  116  124  120  130  123  134  129  126    128 129    134  129  125  129  2024
2025   137  126  137  124  108  106  102  117  125  119  121  107    119 121    130  123  108  121  2025
2026   108  124 **** **** **** **** **** **** **** **** **** ****   **** ***    113 **** **** ****  2026
        """
    )


def test_s02_scan_ignores_ukraine_false_positive():
    strategy = WeatherNOAA()
    markets = [
        Market(
            condition_id="0x1",
            question="Will Ukraine sign a ceasefire this month?",
            tokens=[
                {"token_id": "y1", "outcome": "Yes", "price": "0.70"},
                {"token_id": "n1", "outcome": "No", "price": "0.30"},
            ],
            active=True,
            volume=5000,
        )
    ]
    assert strategy.scan(markets) == []


def test_s02_scan_ignores_character_of_rain_false_positive():
    strategy = WeatherNOAA()
    markets = [
        Market(
            condition_id="0xfilm",
            question="Will Little Amelie or the Character of Rain win Best Animated Feature Film at the 98th Academy Awards?",
            tokens=[
                {"token_id": "yf", "outcome": "Yes", "price": "0.10"},
                {"token_id": "nf", "outcome": "No", "price": "0.90"},
            ],
            active=True,
            volume=5000,
        )
    ]
    assert strategy.scan(markets) == []


def test_s02_scan_includes_expensive_weather_market_for_fade():
    strategy = WeatherNOAA()
    markets = [
        Market(
            condition_id="0x2",
            question="Will Chicago high temperature exceed 80 degrees fahrenheit?",
            tokens=[
                {"token_id": "y2", "outcome": "Yes", "price": "0.70"},
                {"token_id": "n2", "outcome": "No", "price": "0.30"},
            ],
            active=True,
            volume=5000,
        )
    ]
    opportunities = strategy.scan(markets)
    assert len(opportunities) == 1
    assert opportunities[0].metadata["candidate_score"] > 0


def test_s02_analyze_enriches_signal_with_station_and_setup():
    strategy = WeatherNOAA()
    provider = NOAAWeatherProvider()
    provider.set_cached("forecast:chicago", _forecast(70))
    provider.set_cached("griddata:chicago", _grid())
    provider.set_cached(
        "observation:chicago",
        {
            "city": "chicago",
            "station_id": "KORD",
            "station_label": "Chicago O'Hare",
            "timestamp": "2026-03-11T13:00:00+00:00",
            "temperature_c": 18.0,
            "temperature_f": 64.4,
        },
    )
    registry = DataRegistry()
    registry.register(provider)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0x3",
        question="Will Chicago high temperature exceed 80 degrees fahrenheit on March 11?",
        market_price=0.70,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "y3", "outcome": "Yes", "price": "0.70"},
                {"token_id": "n3", "outcome": "No", "price": "0.30"},
            ],
            "volume": 5000,
        },
    )
    signal = strategy.analyze(opp)
    assert signal is not None
    assert signal.token_id == "n3"
    assert signal.metadata["station_id"] == "KORD"
    assert signal.metadata["setup_type"] == "fade_yes"
    assert signal.metadata["city"] == "chicago"
    assert signal.metadata["source_count"] >= 2
    assert signal.metadata["regime"] == "local_hold"
    assert signal.metadata["hold_to_expiry"] is True
    assert float(signal.metadata["take_profit_price"]) >= 0.97

    plan = strategy.build_manual_plan(signal, size=25.0)
    assert plan is not None
    assert plan["hold_to_expiry"] is True
    assert "정산까지 보유" in plan["instruction_kr"]


def test_temperature_contract_parses_compact_bucket():
    contract = WeatherNOAA._extract_temperature_contract(
        "Will the highest temperature in Chicago on March 2 be 38-39°F?"
    )
    assert contract == ("between", 38.0, 39.0)


def test_global_temperature_market_extracts_city_from_question():
    strategy = WeatherNOAA()
    noaa = NOAAWeatherProvider()
    registry = DataRegistry()
    registry.register(noaa)
    strategy.set_data_registry(registry)
    engine = strategy._engine(noaa)
    spec = engine.parse_market(
        "Will the highest temperature in Sao Paulo be 25°C on March 11?",
        description="Resolution source: https://www.wunderground.com/history/daily/br/sao-paulo/SBSP",
        resolution_source="https://www.wunderground.com/history/daily/br/sao-paulo/SBSP",
    )
    assert spec is not None
    assert spec.city == "sao paulo"
    assert spec.settlement_source == "wunderground_daily"
    assert spec.station_id == "SBSP"


def test_s02_global_temperature_question_maps_to_climate_reprice():
    strategy = WeatherNOAA()
    assert (
        strategy._market_regime(
            "Will global temperature increase by between 1.25ºC and 1.29ºC in February 2025?",
            "temperature",
        )
        == "climate_reprice"
    )


def test_s02_global_temperature_anomaly_market_uses_climate_provider():
    strategy = WeatherNOAA()
    climate = GlobalClimateProvider()
    climate.get_monthly_series = lambda: _global_series()
    climate.get_berkeley_monthly_update = lambda *args, **kwargs: None

    registry = DataRegistry()
    registry.register(climate)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0xclimate",
        question="Will global temperature increase by more than 1.10ºC in March 2026?",
        market_price=0.20,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "ycl", "outcome": "Yes", "price": "0.20"},
                {"token_id": "ncl", "outcome": "No", "price": "0.80"},
            ],
            "volume": 10000,
            "description": "Resolution source: NASA GISTEMP and Berkeley Earth monthly anomaly",
            "resolution_source": "NASA GISTEMP and Berkeley Earth monthly anomaly",
            "end_date_iso": "2026-03-31T00:00:00Z",
        },
    )

    signal = strategy.analyze(opp)
    assert signal is not None
    assert signal.metadata["weather_type"] == "global_temperature_anomaly"
    assert signal.metadata["regime"] == "climate_reprice"
    assert signal.metadata["settlement_source"] == "global_climate_monthly"
    assert signal.metadata["mu_c"] > 1.0
    assert signal.metadata["release_state"] == "nowcast_nasa_anchor"


def test_s02_global_temperature_record_market_uses_prior_record_threshold():
    strategy = WeatherNOAA()
    climate = GlobalClimateProvider()
    climate.get_monthly_series = lambda: _global_series()
    climate.get_berkeley_monthly_update = lambda *args, **kwargs: None

    registry = DataRegistry()
    registry.register(climate)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0xrecord",
        question="2026 August hottest on record?",
        market_price=0.10,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "yrec", "outcome": "Yes", "price": "0.10"},
                {"token_id": "nrec", "outcome": "No", "price": "0.90"},
            ],
            "volume": 9000,
            "description": "Resolution source: NASA GISTEMP and Berkeley Earth monthly anomaly",
            "resolution_source": "NASA GISTEMP and Berkeley Earth monthly anomaly",
            "end_date_iso": "2026-08-31T00:00:00Z",
        },
    )

    signal = strategy.analyze(opp)
    assert signal is not None
    assert signal.metadata["weather_type"] == "global_temperature_record"
    assert signal.metadata["record_threshold_c"] == pytest.approx(1.30, abs=1e-6)
    assert signal.metadata["regime"] == "climate_reprice"


def test_s02_no_longshot_price_bump_fallback_for_unparsed_market():
    strategy = WeatherNOAA()
    registry = DataRegistry()
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0xfallback",
        question="Will Atlantis be rediscovered this month?",
        market_price=0.01,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "yf", "outcome": "Yes", "price": "0.01"},
                {"token_id": "nf", "outcome": "No", "price": "0.99"},
            ],
            "volume": 1000,
        },
    )
    assert strategy.analyze(opp) is None


def test_s02_evaluate_opportunity_returns_monitor_reason_when_edge_is_too_small():
    strategy = WeatherNOAA()
    provider = NOAAWeatherProvider()
    provider.set_cached("forecast:chicago", _forecast(80))
    provider.set_cached("griddata:chicago", _grid())
    registry = DataRegistry()
    registry.register(provider)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0xmonitor",
        question="Will Chicago high temperature exceed 80 degrees fahrenheit on March 11?",
        market_price=0.08,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "ym", "outcome": "Yes", "price": "0.08"},
                {"token_id": "nm", "outcome": "No", "price": "0.92"},
            ],
            "volume": 2000,
        },
    )
    evaluation = strategy.evaluate_opportunity(opp)
    assert evaluation["status"] == "monitor"
    assert evaluation["reason_code"] in {"edge_below_required", "confidence_too_low"}


def test_s02_scan_market_universe_includes_watch_only_weather_market():
    strategy = WeatherNOAA()
    markets = [
        Market(
            condition_id="0xwatch",
            question="Will Chicago high temperature exceed 80 degrees fahrenheit?",
            tokens=[
                {"token_id": "yw", "outcome": "Yes", "price": "0.30"},
                {"token_id": "nw", "outcome": "No", "price": "0.70"},
            ],
            active=True,
            volume=5000,
        )
    ]
    opportunities = strategy.scan_market_universe(markets, include_low_score=True)
    assert len(opportunities) == 1
    assert opportunities[0].metadata["scan_status"] in {"candidate", "watch_only"}


def test_s02_celsius_temperature_contract_normalizes_to_fahrenheit_inputs():
    strategy = WeatherNOAA()
    provider = NOAAWeatherProvider()
    provider.city_profile = lambda city, country_code=None: {
        "canonical": "sao paulo",
        "coords": (-23.55, -46.63),
        "station_id": "SBSP",
        "station_label": "Sao Paulo",
        "climate_location_id": None,
        "country_code": "br",
        "forecast_source": "open_meteo",
    }
    provider.set_cached("forecast:sao paulo", _forecast_c(22))
    provider.set_cached(
        "griddata:sao paulo",
        {
            "temperature": {
                "values": [
                    {"validTime": "2026-03-11T13:00:00+00:00/PT1H", "value": 22.0},
                    {"validTime": "2026-03-11T14:00:00+00:00/PT1H", "value": 22.5},
                ]
            },
            "maxTemperature": {
                "values": [
                    {"validTime": "2026-03-11T13:00:00+00:00/PT12H", "value": 22.0},
                ]
            },
        },
    )
    provider.set_cached(
        "observation:sao paulo",
        {
            "city": "sao paulo",
            "station_id": "SBSP",
            "station_label": "Sao Paulo",
            "timestamp": "2026-03-11T13:00:00+00:00",
            "temperature_c": 22.0,
            "temperature_f": 71.6,
        },
    )
    registry = DataRegistry()
    registry.register(provider)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0xsp",
        question="Will the highest temperature in Sao Paulo be 22°C on March 11?",
        market_price=0.40,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "ysp", "outcome": "Yes", "price": "0.40"},
                {"token_id": "nsp", "outcome": "No", "price": "0.60"},
            ],
            "volume": 3000,
            "description": "Resolution source: https://www.wunderground.com/history/daily/br/sao-paulo/SBSP",
            "resolution_source": "https://www.wunderground.com/history/daily/br/sao-paulo/SBSP",
        },
    )
    signal = strategy.analyze(opp)
    assert signal is not None
    assert signal.metadata["mu"] == pytest.approx(71.6, abs=1.0)
    assert 0.0 < signal.metadata["fair_yes_prob"] < 0.5
    assert signal.metadata["side_selected"] == "no"


def test_s02_precipitation_uses_blended_inputs():
    strategy = WeatherNOAA()
    noaa = NOAAWeatherProvider()
    noaa.set_cached("forecast:chicago", _forecast(50))
    noaa.set_cached("griddata:chicago", _grid())
    aviation = AviationWeatherProvider()
    aviation.set_cached(
        "taf:KORD",
        {
            "icaoId": "KORD",
            "fcsts": [
                {
                    "timeFrom": 1773252000,
                    "timeTo": 1773262800,
                    "fcstChange": None,
                    "wxString": "-RA",
                    "probability": None,
                    "visib": 4,
                }
            ],
        },
    )
    registry = DataRegistry()
    registry.register(noaa)
    registry.register(aviation)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0x4",
        question="Will it rain in Chicago on March 11?",
        market_price=0.20,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "y4", "outcome": "Yes", "price": "0.20"},
                {"token_id": "n4", "outcome": "No", "price": "0.80"},
            ],
            "volume": 4000,
        },
    )
    signal = strategy.analyze(opp)
    assert signal is not None
    assert signal.metadata["weather_type"] == "precipitation"
    assert signal.metadata["qpf_prob"] is not None
    assert signal.metadata["source_count"] >= 2


def test_s02_monthly_precipitation_uses_cf6_actuals(monkeypatch):
    import datetime as _dt

    class _FrozenDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 28, 12, 0, 0, tzinfo=tz or _dt.timezone.utc)

    monkeypatch.setattr("core.weather_market_engine.datetime", _FrozenDateTime)

    strategy = WeatherNOAA()
    noaa = NOAAWeatherProvider()
    noaa.set_cached("forecast:new york", _forecast(50, count=72))
    noaa.set_cached(
        "griddata:new york",
        {
            "quantitativePrecipitation": {
                "values": [
                    {"validTime": "2026-03-28T13:00:00+00:00/PT6H", "value": 12.0},
                    {"validTime": "2026-03-29T01:00:00+00:00/PT6H", "value": 8.0},
                ]
            }
        },
    )
    climate = NWSClimateProvider()
    climate.get_month_to_date_summary = lambda *args, **kwargs: {
        "location_id": "LGA",
        "year": 2026,
        "month": 3,
        "precip_in": 1.86,
        "snow_in": 0.0,
        "precip_days": 4,
        "rows": [],
        "last_reported_day": 10,
    }

    registry = DataRegistry()
    registry.register(noaa)
    registry.register(climate)
    strategy.set_data_registry(registry)

    opp = Opportunity(
        market_id="0x5",
        question="Will NYC have between 2 and 3 inches of precipitation in March?",
        market_price=0.35,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "y5", "outcome": "Yes", "price": "0.35"},
                {"token_id": "n5", "outcome": "No", "price": "0.65"},
            ],
            "volume": 4200,
            "description": "Resolves using https://api.weather.gov/products/types/CF6/locations/LGA/latest",
            "resolution_source": "https://api.weather.gov/products/types/CF6/locations/LGA/latest",
        },
    )
    signal = strategy.analyze(opp)
    assert signal is not None
    assert signal.metadata["weather_type"] == "monthly_precipitation"
    assert signal.metadata["actual_precip_in"] == pytest.approx(1.86, abs=1e-3)
    assert signal.metadata["settlement_location_id"] == "LGA"
