"""Route Polymarket weather markets to their actual settlement sources."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


_WUNDERGROUND_STATION_RE = re.compile(
    r"wunderground\.com/history/daily/.+?/([A-Z][A-Z0-9]{2,4})(?:/date/|/?$)",
    re.IGNORECASE,
)
_CLI_LOC_RE = re.compile(r"/products/types/CLI/locations/([A-Z0-9]{3,4})", re.IGNORECASE)
_CF6_LOC_RE = re.compile(r"/products/types/CF6/locations/([A-Z0-9]{3,4})", re.IGNORECASE)
_CLI_CODE_RE = re.compile(r"\bCLI([A-Z0-9]{3,4})\b", re.IGNORECASE)
_CF6_CODE_RE = re.compile(r"\bCF6([A-Z0-9]{3,4})\b", re.IGNORECASE)
_ICAO_RE = re.compile(r"\b(K[A-Z]{3})\b")


@dataclass
class WeatherResolutionProfile:
    source_kind: str
    settlement_metric: str
    rounding_mode: str
    unit: str
    resolution_source: Optional[str] = None
    station_id: Optional[str] = None
    location_id: Optional[str] = None
    publish_schedule: str = "intraday"

    def to_metadata(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_station_id(text: str) -> Optional[str]:
    match = _WUNDERGROUND_STATION_RE.search(text)
    if match:
        return match.group(1).upper()
    match = _ICAO_RE.search(text)
    if match:
        return match.group(1).upper()
    return None


def _extract_location_id(text: str, station_id: Optional[str]) -> Optional[str]:
    for pattern in (_CLI_LOC_RE, _CF6_LOC_RE, _CLI_CODE_RE, _CF6_CODE_RE):
        match = pattern.search(text)
        if match:
            return match.group(1).upper()
    if station_id and station_id.startswith("K") and len(station_id) == 4:
        return station_id[1:]
    return None


def route_weather_resolution(
    question: str,
    description: str = "",
    resolution_source: Optional[str] = None,
) -> WeatherResolutionProfile:
    text = "\n".join(part for part in [question, description, resolution_source or ""] if part)
    text_lower = text.lower()

    if "global temperature increase" in text_lower or "temperature increase" in text_lower:
        settlement_metric = "global_temperature_anomaly"
        rounding_mode = "hundredth_c"
        unit = "C"
    elif "hottest on record" in text_lower:
        settlement_metric = "global_temperature_record"
        rounding_mode = "record_high"
        unit = "C"
    elif "highest temperature" in text_lower:
        settlement_metric = "temperature_max"
        rounding_mode = "nearest_int_f"
        unit = "F"
    elif "lowest temperature" in text_lower:
        settlement_metric = "temperature_min"
        rounding_mode = "nearest_int_f"
        unit = "F"
    elif "how many days" in text_lower or re.search(r"\bexactly\s+\d+\s+days\b", text_lower):
        settlement_metric = "precipitation_days"
        rounding_mode = "gt_zero_precip_day"
        unit = "days"
    elif "snow" in text_lower:
        settlement_metric = "snowfall_total"
        rounding_mode = "hundredth_inch"
        unit = "in"
    else:
        settlement_metric = "precipitation_total"
        rounding_mode = "hundredth_inch"
        unit = "in"

    source_kind = "unknown"
    publish_schedule = "intraday"
    if "nasa gistemp" in text_lower or "berkeley earth" in text_lower:
        source_kind = "global_climate_monthly"
        publish_schedule = "monthly_report"
    elif "wunderground" in text_lower:
        source_kind = "wunderground_daily"
        publish_schedule = "intraday"
    elif "/products/types/cli/" in text_lower or "climate summary" in text_lower or "cli" in text_lower:
        source_kind = "nws_cli_daily"
        publish_schedule = "daily_report"
    elif "/products/types/cf6/" in text_lower or "preliminary local climatological data" in text_lower:
        source_kind = "nws_cf6_monthly"
        publish_schedule = "daily_rollup"
    elif "weather.gov/wrh/climate" in text_lower or "monthly summarized data" in text_lower:
        source_kind = "weather_gov_monthly"
        publish_schedule = "daily_rollup"
    elif "weather.gov" in text_lower:
        source_kind = "weather_gov"

    if source_kind == "unknown" and settlement_metric in {"global_temperature_anomaly", "global_temperature_record"}:
        source_kind = "global_climate_monthly"
        publish_schedule = "monthly_report"

    station_id = _extract_station_id(text)
    location_id = _extract_location_id(text, station_id=station_id)
    if source_kind in {"unknown", "weather_gov"} and settlement_metric in {"precipitation_total", "precipitation_days"}:
        source_kind = "nws_cf6_monthly"
        publish_schedule = "daily_rollup"

    return WeatherResolutionProfile(
        source_kind=source_kind,
        settlement_metric=settlement_metric,
        rounding_mode=rounding_mode,
        unit=unit,
        resolution_source=resolution_source,
        station_id=station_id,
        location_id=location_id,
        publish_schedule=publish_schedule,
    )
