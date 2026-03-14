from core.weather_resolution import route_weather_resolution


def test_routes_wunderground_temperature_market():
    profile = route_weather_resolution(
        "Will the highest temperature in Chicago on March 11 be 45-46°F?",
        resolution_source="https://www.wunderground.com/history/daily/us/il/chicago/KORD/date/2026-03-11",
    )
    assert profile.source_kind == "wunderground_daily"
    assert profile.settlement_metric == "temperature_max"
    assert profile.station_id == "KORD"
    assert profile.location_id == "ORD"
    assert profile.rounding_mode == "nearest_int_f"


def test_routes_cli_and_cf6_precip_markets():
    cli_profile = route_weather_resolution(
        "Will New York get snow on March 11?",
        description="Resolution source: https://api.weather.gov/products/types/CLI/locations/LGA/latest",
    )
    assert cli_profile.source_kind == "nws_cli_daily"
    assert cli_profile.location_id == "LGA"
    assert cli_profile.settlement_metric == "snowfall_total"

    cf6_profile = route_weather_resolution(
        "Will NYC record precipitation on exactly 12 days in December?",
        description="Resolution source: https://api.weather.gov/products/types/CF6/locations/LGA/latest",
    )
    assert cf6_profile.source_kind == "nws_cf6_monthly"
    assert cf6_profile.location_id == "LGA"
    assert cf6_profile.settlement_metric == "precipitation_days"
    assert cf6_profile.rounding_mode == "gt_zero_precip_day"
