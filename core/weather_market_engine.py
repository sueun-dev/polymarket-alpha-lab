"""Shared weather-market parsing and fair-value estimation helpers."""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.weather_resolution import route_weather_resolution


MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        return None


def extract_resolution_country_code(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = re.search(r"wunderground\.com/history/daily/([a-z]{2})/", raw, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def extract_target_date(text: str) -> Optional[date]:
    q = text.lower()
    match = re.search(r"on\s+([a-z]+)\s+(\d{1,2})(?:,?\s*(\d{4}))?", q)
    if not match:
        return None
    month = MONTH_MAP.get(match.group(1))
    if month is None:
        return None
    day = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else datetime.now(timezone.utc).year
    try:
        return date(year, month, day)
    except Exception:
        return None


def extract_target_month(text: str, end_date_iso: Optional[str] = None) -> Tuple[Optional[int], Optional[int]]:
    q = text.lower()
    parsed_end = parse_iso_date(end_date_iso)
    base_year = parsed_end.year if parsed_end is not None else datetime.now(timezone.utc).year
    prefix_match = re.search(r"\b(\d{4})\s+([a-z]+)\b", q)
    if prefix_match:
        month = MONTH_MAP.get(prefix_match.group(2))
        if month is not None:
            return month, int(prefix_match.group(1))
    inline_match = re.search(r"\b([a-z]+)\s+(\d{4})\b", q)
    if inline_match:
        month = MONTH_MAP.get(inline_match.group(1))
        if month is not None:
            return month, int(inline_match.group(2))
    for match in re.finditer(r"\b(?:in|during|for)\s+([a-z]+)(?:\s+(\d{4}))?\b", q):
        month = MONTH_MAP.get(match.group(1))
        if month is None:
            continue
        year = int(match.group(2)) if match.group(2) else base_year
        return month, year
    return None, None


def extract_city_phrase(text: str) -> Optional[str]:
    raw = " ".join(str(text or "").split())
    patterns = [
        r"highest temperature in ([a-zA-Z .'-]+?) be\b",
        r"lowest temperature in ([a-zA-Z .'-]+?) be\b",
        r"will ([a-zA-Z .'-]+?) (?:high|low) temperature\b",
        r"will it (?:rain|snow) in ([a-zA-Z .'-]+?)\b",
        r"will ([a-zA-Z .'-]+?) have .* precipitation\b",
        r"how many days will ([a-zA-Z .'-]+?) record precipitation\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if not match:
            continue
        group = match.group(1)
        cleaned = re.sub(r"\s+", " ", group).strip(" ?.,")
        if cleaned:
            return cleaned.lower()
    return None


def period_date(period: dict) -> Optional[date]:
    start = period.get("startTime")
    if not start:
        return None
    try:
        return datetime.fromisoformat(str(start).replace("Z", "+00:00")).date()
    except Exception:
        return None


def select_periods_for_target(forecast: List[dict], target_date: Optional[date], horizon_hours: int) -> List[dict]:
    if target_date is not None:
        selected = [p for p in forecast if period_date(p) == target_date]
        if selected:
            return selected
    return forecast[:horizon_hours]


def extract_temperatures(periods: List[dict]) -> List[float]:
    out: List[float] = []
    for period in periods:
        raw = period.get("temperature")
        if raw is None:
            continue
        try:
            value = float(raw)
        except Exception:
            continue
        unit = str(period.get("temperatureUnit", "")).strip().upper()
        if unit == "C":
            converted = c_to_f(value)
            if converted is None:
                continue
            value = float(converted)
        out.append(value)
    return out


def extract_temperature(text: str) -> Optional[float]:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°|degrees?|f|fahrenheit|celsius)", text.lower())
    if match:
        return float(match.group(1))
    return None


def extract_temperature_contract(text: str) -> Optional[Tuple[str, float, Optional[float]]]:
    text = text.lower()
    unit = r"(?:°\s*[fc]|degrees?|fahrenheit|celsius|f|c)?"

    between_patterns = [
        r"between\s+(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)",
        rf"be\s+(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)\s*{unit}",
    ]
    for pattern in between_patterns:
        match = re.search(pattern, text)
        if match:
            lo = float(match.group(1))
            hi = float(match.group(2))
            if lo > hi:
                lo, hi = hi, lo
            return "between", lo, hi

    below_patterns = [
        rf"(-?\d+(?:\.\d+)?)\s*{unit}\s*or\s*(?:below|lower|less|under)",
        rf"(?:below|under|less\s+than)\s+(-?\d+(?:\.\d+)?)\s*{unit}",
    ]
    for pattern in below_patterns:
        match = re.search(pattern, text)
        if match:
            return "le", float(match.group(1)), None

    above_patterns = [
        rf"(-?\d+(?:\.\d+)?)\s*{unit}\s*or\s*(?:higher|above|more|over)",
        rf"(?:above|over|higher\s+than|exceed|at\s+least)\s+(-?\d+(?:\.\d+)?)\s*{unit}",
    ]
    for pattern in above_patterns:
        match = re.search(pattern, text)
        if match:
            return "ge", float(match.group(1)), None

    exact_patterns = [
        rf"be\s+(-?\d+(?:\.\d+)?)\s*{unit}\s+on\b",
        rf"be\s+exactly\s+(-?\d+(?:\.\d+)?)\s*{unit}",
    ]
    for pattern in exact_patterns:
        match = re.search(pattern, text)
        if match:
            return "eq", float(match.group(1)), None
    return None


def question_uses_celsius(text: str) -> bool:
    text = text.lower()
    return "°c" in text or "celsius" in text or re.search(r"\b\d+(?:\.\d+)?\s*c\b", text) is not None


def normalize_temperature_contract_to_f(
    contract: Tuple[str, float, Optional[float]],
    *,
    uses_celsius: bool,
) -> Tuple[str, float, Optional[float]]:
    if not uses_celsius:
        return contract
    ctype, low, high = contract
    low_f = c_to_f(low)
    high_f = c_to_f(high) if high is not None else None
    return ctype, float(low_f if low_f is not None else low), None if high_f is None else float(high_f)


def extract_horizon_hours(text: str) -> int:
    q = text.lower()
    if "tomorrow" in q:
        return 24
    hour_match = re.search(r"next\s+(\d{1,2})\s*hours?", q)
    if hour_match:
        try:
            value = int(hour_match.group(1))
        except Exception:
            value = 24
        return max(1, min(value, 48))
    return 24


def extract_numeric_contract(text: str, unit_pattern: str = "") -> Optional[Tuple[str, float, Optional[float]]]:
    text = text.lower()
    unit = rf"(?:\s*{unit_pattern})?" if unit_pattern else ""
    between_patterns = [
        rf"between\s+(-?\d+(?:\.\d+)?)\s*(?:-|to|and)\s*(-?\d+(?:\.\d+)?){unit}",
    ]
    for pattern in between_patterns:
        match = re.search(pattern, text)
        if match:
            lo = float(match.group(1))
            hi = float(match.group(2))
            if lo > hi:
                lo, hi = hi, lo
            return "between", lo, hi

    below_patterns = [
        rf"(?:below|under|less\s+than|fewer\s+than|at\s+most|no\s+more\s+than)\s+(-?\d+(?:\.\d+)?){unit}",
        rf"(-?\d+(?:\.\d+)?){unit}\s+or\s+(?:below|less)",
    ]
    for pattern in below_patterns:
        match = re.search(pattern, text)
        if match:
            return "le", float(match.group(1)), None

    above_patterns = [
        rf"(?:above|over|greater\s+than|more\s+than|at\s+least|no\s+less\s+than)\s+(-?\d+(?:\.\d+)?){unit}",
        rf"(-?\d+(?:\.\d+)?){unit}\s+or\s+(?:above|higher|more)",
    ]
    for pattern in above_patterns:
        match = re.search(pattern, text)
        if match:
            return "ge", float(match.group(1)), None

    exact_patterns = [
        rf"exactly\s+(-?\d+(?:\.\d+)?){unit}",
        rf"be\s+(-?\d+(?:\.\d+)?){unit}\b",
    ]
    for pattern in exact_patterns:
        match = re.search(pattern, text)
        if match:
            return "eq", float(match.group(1)), None
    return None


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def temperature_contract_probability(mu: float, sigma: float, contract: Tuple[str, float, Optional[float]]) -> float:
    ctype, a, b = contract
    if sigma <= 0:
        sigma = 1.0

    def cdf(value: float) -> float:
        return normal_cdf((value - mu) / sigma)

    if ctype == "between" and b is not None:
        lo = a - 0.5
        hi = b + 0.5
        return clamp(cdf(hi) - cdf(lo))
    if ctype == "le":
        return clamp(cdf(a + 0.5))
    if ctype == "ge":
        return clamp(1.0 - cdf(a - 0.5))
    if ctype == "eq":
        return clamp(cdf(a + 0.5) - cdf(a - 0.5))
    return 0.5


def continuous_contract_probability(
    mu: float,
    sigma: float,
    contract: Tuple[str, float, Optional[float]],
    exact_width: float = 0.05,
) -> float:
    if sigma <= 0:
        sigma = 0.05

    def cdf(value: float) -> float:
        return normal_cdf((value - mu) / sigma)

    ctype, a, b = contract
    if ctype == "between" and b is not None:
        return clamp(cdf(b) - cdf(a))
    if ctype == "le":
        return clamp(cdf(a))
    if ctype == "ge":
        return clamp(1.0 - cdf(a))
    if ctype == "eq":
        return clamp(cdf(a + exact_width) - cdf(a - exact_width))
    return 0.5


def discrete_contract_probability(
    probabilities: List[float],
    base_count: int,
    contract: Tuple[str, float, Optional[float]],
) -> float:
    distribution = [1.0]
    for prob in probabilities:
        p = clamp(prob)
        next_dist = [0.0] * (len(distribution) + 1)
        for idx, mass in enumerate(distribution):
            next_dist[idx] += mass * (1.0 - p)
            next_dist[idx + 1] += mass * p
        distribution = next_dist

    ctype, a, b = contract
    if ctype == "eq":
        target = int(round(a)) - base_count
        return distribution[target] if 0 <= target < len(distribution) else 0.0
    if ctype == "between" and b is not None:
        lo = int(math.ceil(a)) - base_count
        hi = int(math.floor(b)) - base_count
        lo = max(0, lo)
        hi = min(len(distribution) - 1, hi)
        if lo > hi:
            return 0.0
        return sum(distribution[lo : hi + 1])
    if ctype == "le":
        hi = min(len(distribution) - 1, int(math.floor(a)) - base_count)
        if hi < 0:
            return 0.0
        return sum(distribution[: hi + 1])
    if ctype == "ge":
        lo = max(0, int(math.ceil(a)) - base_count)
        if lo >= len(distribution):
            return 0.0
        return sum(distribution[lo:])
    return 0.5


def c_to_f(value_c: Optional[float]) -> Optional[float]:
    if value_c is None:
        return None
    return (float(value_c) * 9.0 / 5.0) + 32.0


def mm_to_inches(value_mm: Optional[float]) -> Optional[float]:
    if value_mm is None:
        return None
    return float(value_mm) / 25.4


def parse_valid_time_range(valid_time: str) -> Optional[Tuple[datetime, datetime]]:
    match = re.match(r"^(.+?)/P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$", str(valid_time))
    if not match:
        return None
    try:
        start = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    except Exception:
        return None
    days = int(match.group(2) or 0)
    hours = int(match.group(3) or 0)
    minutes = int(match.group(4) or 0)
    duration_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
    if duration_seconds <= 0:
        duration_seconds = 3600
    end = datetime.fromtimestamp(start.timestamp() + duration_seconds, tz=start.tzinfo or timezone.utc)
    return start, end


@dataclass
class WeatherContractSpec:
    city: str
    canonical_city: str
    country_code: Optional[str]
    market_type: str
    contract_type: str
    target_date: Optional[date]
    horizon_hours: int
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None
    forecast_stat: str = "max"
    precip_kind: str = "any"
    station_id: Optional[str] = None
    station_label: Optional[str] = None
    source_hint: str = "weather.gov"
    target_month: Optional[int] = None
    target_year: Optional[int] = None
    resolution_source: Optional[str] = None
    settlement_source: str = "forecast"
    settlement_metric: str = ""
    settlement_location_id: Optional[str] = None
    settlement_rounding: str = "none"

    def to_metadata(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["target_date"] = self.target_date.isoformat() if self.target_date else None
        return payload


@dataclass
class WeatherFairValue:
    fair_yes_prob: float
    confidence: float
    model: str
    market_type: str
    station_id: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)


class WeatherMarketEngine:
    """Market parser and fair-value engine for weather contracts."""

    WEATHER_PATTERNS = [
        re.compile(r"\bweather\b"),
        re.compile(r"\btemperature\b"),
        re.compile(r"\btemperature increase\b"),
        re.compile(r"\bglobal temperature\b"),
        re.compile(r"\bdegrees?\b"),
        re.compile(r"\brain\b"),
        re.compile(r"\bsnow\b"),
        re.compile(r"\bprecipitation\b"),
        re.compile(r"\bforecast\b"),
        re.compile(r"\bhottest on record\b"),
    ]
    PRECIP_PATTERNS = [
        re.compile(r"\brain\b"),
        re.compile(r"\bsnow\b"),
        re.compile(r"\bprecipitation\b"),
        re.compile(r"\bstorm\b"),
        re.compile(r"\bshowers?\b"),
    ]
    TEMP_PATTERNS = [
        re.compile(r"\btemperature\b"),
        re.compile(r"\btemperature increase\b"),
        re.compile(r"\bglobal temperature\b"),
        re.compile(r"\bdegrees?\b"),
        re.compile(r"\bfahrenheit\b"),
        re.compile(r"\bcelsius\b"),
        re.compile(r"\bhigh(?:est)?\b"),
        re.compile(r"\blow(?:est)?\b"),
        re.compile(r"\bheat\b"),
        re.compile(r"\bcold\b"),
        re.compile(r"\bhottest on record\b"),
    ]

    def __init__(
        self,
        provider: Any,
        kernel: Any,
        aviation_provider: Any = None,
        climate_provider: Any = None,
        global_climate_provider: Any = None,
    ) -> None:
        self.provider = provider
        self.kernel = kernel
        self.aviation_provider = aviation_provider
        self.climate_provider = climate_provider
        self.global_climate_provider = global_climate_provider

    def is_weather_market(self, question: str, description: str = "", category: str = "") -> bool:
        if str(category).strip().lower() == "weather":
            return True
        text = f"{question}\n{description}".lower()
        return any(pattern.search(text) for pattern in self.WEATHER_PATTERNS)

    def parse_market(
        self,
        question: str,
        description: str = "",
        end_date_iso: Optional[str] = None,
        resolution_source: Optional[str] = None,
    ) -> Optional[WeatherContractSpec]:
        text = " ".join(x for x in [question, description] if x).lower()
        if not self.is_weather_market(question, description):
            return None
        resolution_profile = route_weather_resolution(question, description, resolution_source)

        city = extract_city_phrase(question)
        country_code = extract_resolution_country_code(resolution_source) or extract_resolution_country_code(description)
        profile: Optional[Dict[str, Any]] = None
        if city is None and self.provider is not None and hasattr(self.provider, "extract_city_from_question"):
            city = self.provider.extract_city_from_question(text)
        if city and hasattr(self.provider, "city_profile"):
            profile = self.provider.city_profile(city, country_code=country_code)

        canonical_city = city or ""
        station_id = resolution_profile.station_id
        station_label = None
        climate_location_id = resolution_profile.location_id
        if profile:
            canonical_city = str(profile.get("canonical", city or ""))
            country_code = str(profile.get("country_code") or country_code or "").lower() or None
            station_id = station_id or profile.get("station_id")
            station_label = profile.get("station_label")
            climate_location_id = climate_location_id or profile.get("climate_location_id")

        target_month, target_year = extract_target_month(text, end_date_iso=end_date_iso)
        if resolution_profile.settlement_metric in {"global_temperature_anomaly", "global_temperature_record"}:
            if target_month is None or target_year is None:
                return None
            if resolution_profile.settlement_metric == "global_temperature_record":
                return WeatherContractSpec(
                    city="",
                    canonical_city="",
                    country_code=None,
                    market_type="global_temperature_record",
                    contract_type="record_high",
                    target_date=None,
                    horizon_hours=0,
                    source_hint=resolution_profile.source_kind,
                    target_month=target_month,
                    target_year=target_year,
                    resolution_source=resolution_profile.resolution_source,
                    settlement_source=resolution_profile.source_kind or "global_climate_monthly",
                    settlement_metric=resolution_profile.settlement_metric,
                    settlement_location_id=None,
                    settlement_rounding=resolution_profile.rounding_mode,
                )
            contract = extract_numeric_contract(
                text,
                unit_pattern=r"(?:º?c|°?c|degrees?\s*c(?:elsius)?)",
            ) or extract_numeric_contract(text)
            if contract is None:
                return None
            return WeatherContractSpec(
                city="",
                canonical_city="",
                country_code=None,
                market_type="global_temperature_anomaly",
                contract_type=contract[0],
                target_date=None,
                horizon_hours=0,
                threshold_low=contract[1],
                threshold_high=contract[2],
                source_hint=resolution_profile.source_kind,
                target_month=target_month,
                target_year=target_year,
                resolution_source=resolution_profile.resolution_source,
                settlement_source=resolution_profile.source_kind or "global_climate_monthly",
                settlement_metric=resolution_profile.settlement_metric,
                settlement_location_id=None,
                settlement_rounding=resolution_profile.rounding_mode,
            )

        target_date = extract_target_date(text) or parse_iso_date(end_date_iso)
        if target_date is not None:
            days_out = (target_date - datetime.now(timezone.utc).date()).days
            if days_out > 6:
                return None

        horizon_hours = extract_horizon_hours(text)
        uses_celsius = question_uses_celsius(text)

        if resolution_profile.settlement_metric == "precipitation_days" and target_month is not None:
            contract = extract_numeric_contract(text, unit_pattern=r"(?:days?)")
            if contract is not None:
                return WeatherContractSpec(
                    city=city or "",
                    canonical_city=canonical_city,
                    country_code=country_code,
                    market_type="monthly_precip_days",
                    contract_type=contract[0],
                    target_date=target_date,
                    horizon_hours=horizon_hours,
                    threshold_low=contract[1],
                    threshold_high=contract[2],
                    station_id=station_id,
                    station_label=station_label,
                    source_hint=resolution_profile.source_kind,
                    target_month=target_month,
                    target_year=target_year,
                    resolution_source=resolution_profile.resolution_source,
                    settlement_source=resolution_profile.source_kind,
                    settlement_metric=resolution_profile.settlement_metric,
                    settlement_location_id=climate_location_id,
                    settlement_rounding=resolution_profile.rounding_mode,
                )

        if target_month is not None and ("precipitation" in text or "rain" in text):
            contract = extract_numeric_contract(text, unit_pattern=r"(?:inches?|inch)")
            if contract is not None:
                return WeatherContractSpec(
                    city=city or "",
                    canonical_city=canonical_city,
                    country_code=country_code,
                    market_type="monthly_precipitation",
                    contract_type=contract[0],
                    target_date=target_date,
                    horizon_hours=horizon_hours,
                    threshold_low=contract[1],
                    threshold_high=contract[2],
                    station_id=station_id,
                    station_label=station_label,
                    source_hint=resolution_profile.source_kind,
                    target_month=target_month,
                    target_year=target_year,
                    resolution_source=resolution_profile.resolution_source,
                    settlement_source=resolution_profile.source_kind,
                    settlement_metric=resolution_profile.settlement_metric,
                    settlement_location_id=climate_location_id,
                    settlement_rounding=resolution_profile.rounding_mode,
                )

        if any(pattern.search(text) for pattern in self.TEMP_PATTERNS):
            if not re.search(r"\b(?:highest|lowest)\s+temperature\s+in\b", text) and not re.search(r"\b(?:high|low)\s+temperature\b", text):
                return None
            contract = extract_temperature_contract(text)
            if contract is None:
                threshold = extract_temperature(text)
                if threshold is None:
                    return None
                if re.search(r"\b(?:above|over|higher|exceed|at least)\b", text):
                    contract = ("ge", threshold, None)
                elif re.search(r"\b(?:below|under|lower|less)\b", text):
                    contract = ("le", threshold, None)
                else:
                    contract = ("eq", threshold, None)
            contract = normalize_temperature_contract_to_f(contract, uses_celsius=uses_celsius)

            forecast_stat = "min" if re.search(r"\blow(?:est)?\b", text) and not re.search(r"\bhigh(?:est)?\b", text) else "max"
            return WeatherContractSpec(
                city=city or "",
                canonical_city=canonical_city,
                country_code=country_code,
                market_type="temperature",
                contract_type=contract[0],
                target_date=target_date,
                horizon_hours=horizon_hours,
                threshold_low=contract[1],
                threshold_high=contract[2],
                forecast_stat=forecast_stat,
                station_id=station_id,
                station_label=station_label,
                source_hint=resolution_profile.source_kind,
                resolution_source=resolution_profile.resolution_source,
                settlement_source=resolution_profile.source_kind,
                settlement_metric=resolution_profile.settlement_metric,
                settlement_location_id=climate_location_id,
                settlement_rounding=resolution_profile.rounding_mode,
            )

        if any(pattern.search(text) for pattern in self.PRECIP_PATTERNS):
            if not (
                re.search(r"\bwill it (?:rain|snow) in\b", text)
                or re.search(r"\bprecipitation in\b", text)
                or re.search(r"\brecord precipitation\b", text)
            ):
                return None
            if re.search(r"\bexactly\s+\d+\s+days?\b", text) or re.search(r"\bhow many days\b", text):
                return None
            precip_kind = "any"
            if re.search(r"\bsnow\b", text):
                precip_kind = "snow"
            elif re.search(r"\brain\b", text):
                precip_kind = "rain"
            return WeatherContractSpec(
                city=city or "",
                canonical_city=canonical_city,
                country_code=country_code,
                market_type="precipitation",
                contract_type="event",
                target_date=target_date,
                horizon_hours=horizon_hours,
                precip_kind=precip_kind,
                station_id=station_id,
                station_label=station_label,
                source_hint=resolution_profile.source_kind,
                resolution_source=resolution_profile.resolution_source,
                settlement_source=resolution_profile.source_kind,
                settlement_metric=resolution_profile.settlement_metric,
                settlement_location_id=climate_location_id,
                settlement_rounding=resolution_profile.rounding_mode,
            )

        return None

    def _grid_values_for_target(self, grid_data: Dict[str, Any], field_name: str, target_date: Optional[date], hours: int) -> List[float]:
        raw_field = grid_data.get(field_name)
        if not isinstance(raw_field, dict):
            return []
        values = raw_field.get("values")
        if not isinstance(values, list):
            return []

        now = datetime.now(timezone.utc)
        window_start = now
        window_end = datetime.fromtimestamp(now.timestamp() + (max(1, hours) * 3600), tz=timezone.utc)
        if target_date is not None:
            window_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
            window_end = datetime.fromtimestamp(window_start.timestamp() + 86400, tz=timezone.utc)

        out: List[float] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            parsed = parse_valid_time_range(str(item.get("validTime") or ""))
            if parsed is None:
                continue
            start, end = parsed
            if end <= window_start or start >= window_end:
                continue
            raw_value = item.get("value")
            if raw_value is None:
                continue
            try:
                out.append(float(raw_value))
            except Exception:
                continue
        return out

    def _grid_values_for_range(
        self,
        grid_data: Dict[str, Any],
        field_name: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[float]:
        raw_field = grid_data.get(field_name)
        if not isinstance(raw_field, dict):
            return []
        values = raw_field.get("values")
        if not isinstance(values, list):
            return []

        out: List[float] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            parsed = parse_valid_time_range(str(item.get("validTime") or ""))
            if parsed is None:
                continue
            valid_start, valid_end = parsed
            if valid_end <= start_dt or valid_start >= end_dt:
                continue
            raw_value = item.get("value")
            if raw_value is None:
                continue
            try:
                out.append(float(raw_value))
            except Exception:
                continue
        return out

    @staticmethod
    def _period_bounds(period: Dict[str, Any]) -> Optional[Tuple[datetime, datetime]]:
        start = period.get("startTime")
        if not start:
            return None
        end = period.get("endTime")
        try:
            start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            if end:
                end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            else:
                end_dt = datetime.fromtimestamp(start_dt.timestamp() + 3600, tz=start_dt.tzinfo or timezone.utc)
        except Exception:
            return None
        return start_dt, end_dt

    def _forecast_periods_in_range(
        self,
        forecast: List[Dict[str, Any]],
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for period in forecast:
            if not isinstance(period, dict):
                continue
            bounds = self._period_bounds(period)
            if bounds is None:
                continue
            valid_start, valid_end = bounds
            if valid_end <= start_dt or valid_start >= end_dt:
                continue
            out.append(period)
        return out

    @staticmethod
    def _period_precip_probability(period: Dict[str, Any]) -> float:
        pop_obj = period.get("probabilityOfPrecipitation")
        if not isinstance(pop_obj, dict):
            return 0.0
        raw = pop_obj.get("value")
        try:
            return clamp(float(raw) / 100.0)
        except Exception:
            return 0.0

    def _monthly_precip_total_fair_value(
        self,
        spec: WeatherContractSpec,
        forecast: List[Dict[str, Any]],
        grid_data: Optional[Dict[str, Any]],
    ) -> Optional[WeatherFairValue]:
        if self.climate_provider is None or spec.target_month is None or spec.target_year is None:
            return None
        today = datetime.now(timezone.utc).date()
        if spec.target_month != today.month or spec.target_year != today.year:
            return None
        location_id = spec.settlement_location_id
        if not location_id:
            return None
        summary = self.climate_provider.get_month_to_date_summary(
            location_id,
            target_year=spec.target_year,
            target_month=spec.target_month,
        )
        if not isinstance(summary, dict):
            return None

        month_end_day = date(spec.target_year, spec.target_month, 1).replace(day=28)
        while True:
            try:
                month_end_day = month_end_day.replace(day=month_end_day.day + 1)
            except ValueError:
                break
        month_end = month_end_day
        remaining_days = (month_end - today).days + 1
        if remaining_days > 7:
            return None

        start_dt = datetime.now(timezone.utc)
        end_dt = datetime(spec.target_year, spec.target_month, month_end.day, 23, 59, 59, tzinfo=timezone.utc)
        qpf_inches = 0.0
        if isinstance(grid_data, dict):
            qpf_values = self._grid_values_for_range(grid_data, "quantitativePrecipitation", start_dt, end_dt)
            qpf_inches = sum(mm_to_inches(value) or 0.0 for value in qpf_values)
        if qpf_inches <= 0:
            periods = self._forecast_periods_in_range(forecast, start_dt, end_dt)
            qpf_inches = sum(self._period_precip_probability(period) * 0.03 for period in periods)

        actual_precip = float(summary.get("precip_in") or 0.0)
        mu_final = actual_precip + qpf_inches
        sigma = max(0.05, 0.06 + (0.35 * math.sqrt(max(0.05, qpf_inches))) + (remaining_days * 0.012))
        contract = (spec.contract_type, float(spec.threshold_low or 0.0), spec.threshold_high)
        fair_yes = continuous_contract_probability(mu_final, sigma, contract, exact_width=0.025)
        confidence = clamp(
            0.36
            + (0.12 * min(1.0, float(summary.get("last_reported_day") or 0) / 10.0))
            + (0.16 * min(1.0, qpf_inches / 0.5))
            + (0.08 * min(1.0, 8 - remaining_days) / 7.0),
            0.28,
            0.88,
        )
        return WeatherFairValue(
            fair_yes_prob=fair_yes,
            confidence=confidence,
            model="s02_weather_engine_v4",
            market_type=spec.market_type,
            station_id=spec.station_id,
            details={
                "actual_precip_in": round(actual_precip, 4),
                "remaining_qpf_in": round(qpf_inches, 4),
                "mu_final_precip_in": round(mu_final, 4),
                "sigma_precip_in": round(sigma, 4),
                "remaining_days": remaining_days,
                "settlement_location_id": location_id,
                "settlement_source": spec.settlement_source,
                "last_reported_day": int(summary.get("last_reported_day") or 0),
                "source_count": 2 if qpf_inches > 0 else 1,
            },
        )

    def _monthly_precip_days_fair_value(
        self,
        spec: WeatherContractSpec,
        forecast: List[Dict[str, Any]],
    ) -> Optional[WeatherFairValue]:
        if self.climate_provider is None or spec.target_month is None or spec.target_year is None:
            return None
        today = datetime.now(timezone.utc).date()
        if spec.target_month != today.month or spec.target_year != today.year:
            return None
        location_id = spec.settlement_location_id
        if not location_id:
            return None
        summary = self.climate_provider.get_month_to_date_summary(
            location_id,
            target_year=spec.target_year,
            target_month=spec.target_month,
        )
        if not isinstance(summary, dict):
            return None

        month_end_day = date(spec.target_year, spec.target_month, 1).replace(day=28)
        while True:
            try:
                month_end_day = month_end_day.replace(day=month_end_day.day + 1)
            except ValueError:
                break
        month_end = month_end_day
        remaining_days = (month_end - today).days + 1
        if remaining_days > 7:
            return None

        start_dt = datetime.now(timezone.utc)
        end_dt = datetime(spec.target_year, spec.target_month, month_end.day, 23, 59, 59, tzinfo=timezone.utc)
        periods = self._forecast_periods_in_range(forecast, start_dt, end_dt)
        if not periods:
            return None

        daily_complements: Dict[date, float] = {}
        for period in periods:
            bounds = self._period_bounds(period)
            if bounds is None:
                continue
            valid_start, _ = bounds
            day_key = valid_start.date()
            prob = self._period_precip_probability(period)
            if day_key not in daily_complements:
                daily_complements[day_key] = 1.0
            daily_complements[day_key] *= (1.0 - prob)

        daily_probs = [1.0 - daily_complements[key] for key in sorted(daily_complements.keys())]
        actual_days = int(summary.get("precip_days") or 0)
        contract = (spec.contract_type, float(spec.threshold_low or 0.0), spec.threshold_high)
        fair_yes = discrete_contract_probability(daily_probs, actual_days, contract)
        mean_remaining = sum(daily_probs)
        confidence = clamp(
            0.38
            + (0.10 * min(1.0, float(summary.get("last_reported_day") or 0) / 10.0))
            + (0.16 * min(1.0, len(daily_probs) / 7.0))
            + (0.10 * abs(fair_yes - 0.5)),
            0.30,
            0.87,
        )
        return WeatherFairValue(
            fair_yes_prob=fair_yes,
            confidence=confidence,
            model="s02_weather_engine_v4",
            market_type=spec.market_type,
            station_id=spec.station_id,
            details={
                "actual_precip_days": actual_days,
                "expected_remaining_precip_days": round(mean_remaining, 4),
                "remaining_days": remaining_days,
                "forecast_precip_day_probs": [round(value, 4) for value in daily_probs],
                "settlement_location_id": location_id,
                "settlement_source": spec.settlement_source,
                "last_reported_day": int(summary.get("last_reported_day") or 0),
                "source_count": 2,
            },
        )

    def _provider_call(self, method_name: str, city: str, country_code: Optional[str] = None) -> Any:
        if self.provider is None or not hasattr(self.provider, method_name):
            return None
        method = getattr(self.provider, method_name)
        if country_code:
            try:
                return method(city, country_code=country_code)
            except TypeError:
                return method(city)
        return method(city)

    def _current_observed_temp_f(self, spec: WeatherContractSpec) -> Tuple[Optional[float], Dict[str, Optional[float]]]:
        noaa_temp = None
        aviation_temp = None
        city_key = spec.city or spec.canonical_city
        observation = self._provider_call("get_latest_observation", city_key, country_code=spec.country_code)
        if isinstance(observation, dict):
            raw = observation.get("temperature_f")
            if raw is not None:
                try:
                    noaa_temp = float(raw)
                except Exception:
                    noaa_temp = None
        if self.aviation_provider is not None and spec.station_id and hasattr(self.aviation_provider, "latest_temperature_f"):
            raw = self.aviation_provider.latest_temperature_f(spec.station_id)
            if raw is not None:
                try:
                    aviation_temp = float(raw)
                except Exception:
                    aviation_temp = None

        best = None
        for candidate in [noaa_temp, aviation_temp]:
            if candidate is None:
                continue
            best = candidate if best is None else max(best, candidate)
        return best, {"noaa_observed_temp_f": noaa_temp, "aviation_observed_temp_f": aviation_temp}

    def _global_temperature_fair_value(self, spec: WeatherContractSpec) -> Optional[WeatherFairValue]:
        if self.global_climate_provider is None or spec.target_month is None or spec.target_year is None:
            return None
        estimate = self.global_climate_provider.estimate_monthly_anomaly(
            target_year=spec.target_year,
            target_month=spec.target_month,
        )
        if not isinstance(estimate, dict):
            return None
        mu_c = float(estimate.get("mu_c") or 0.0)
        sigma_c = max(0.005, float(estimate.get("sigma_c") or 0.05))
        is_published = bool(estimate.get("is_published"))
        actual_c_raw = estimate.get("actual_c")
        actual_c = None if actual_c_raw is None else float(actual_c_raw)
        confidence = clamp(float(estimate.get("confidence") or (0.99 if is_published else 0.42)), 0.25, 0.99)

        if spec.market_type == "global_temperature_record":
            threshold_c = self.global_climate_provider.record_threshold_c(spec.target_year, spec.target_month)
            if threshold_c is None:
                return None
            if is_published and actual_c is not None:
                fair_yes = 1.0 if actual_c > threshold_c else 0.0
                confidence = 0.99
            else:
                fair_yes = clamp(1.0 - normal_cdf((threshold_c - mu_c) / sigma_c))
            details = {
                "mu_c": round(mu_c, 4),
                "sigma_c": round(sigma_c, 4),
                "actual_c": None if actual_c is None else round(actual_c, 4),
                "record_threshold_c": round(float(threshold_c), 4),
                "latest_published_year": estimate.get("latest_year"),
                "latest_published_month": estimate.get("latest_month"),
                "settlement_source": spec.settlement_source,
                "source_count": int(estimate.get("source_count") or 1),
                "is_published": is_published,
                "release_state": estimate.get("release_state"),
                "nasa_published": bool(estimate.get("nasa_published")),
                "berkeley_published": bool(estimate.get("berkeley_published")),
                "months_ahead": int(estimate.get("months_ahead") or 0),
            }
            return WeatherFairValue(
                fair_yes_prob=fair_yes,
                confidence=confidence,
                model="s02_global_climate_v1",
                market_type=spec.market_type,
                station_id=None,
                details=details,
            )

        contract = (spec.contract_type, float(spec.threshold_low or 0.0), spec.threshold_high)
        if is_published and actual_c is not None:
            fair_yes = continuous_contract_probability(actual_c, 0.0005, contract, exact_width=0.005)
            confidence = 0.99
        else:
            fair_yes = continuous_contract_probability(mu_c, sigma_c, contract, exact_width=0.005)
        return WeatherFairValue(
            fair_yes_prob=fair_yes,
            confidence=confidence,
            model="s02_global_climate_v1",
            market_type=spec.market_type,
            station_id=None,
            details={
                "mu_c": round(mu_c, 4),
                "sigma_c": round(sigma_c, 4),
                "actual_c": None if actual_c is None else round(actual_c, 4),
                "latest_published_year": estimate.get("latest_year"),
                "latest_published_month": estimate.get("latest_month"),
                "settlement_source": spec.settlement_source,
                "source_count": int(estimate.get("source_count") or 1),
                "is_published": is_published,
                "release_state": estimate.get("release_state"),
                "nasa_published": bool(estimate.get("nasa_published")),
                "berkeley_published": bool(estimate.get("berkeley_published")),
                "months_ahead": int(estimate.get("months_ahead") or 0),
            },
        )

    def fair_value(self, spec: WeatherContractSpec) -> Optional[WeatherFairValue]:
        if spec.market_type in {"global_temperature_anomaly", "global_temperature_record"}:
            return self._global_temperature_fair_value(spec)
        if self.provider is None:
            return None
        city_key = spec.city or spec.canonical_city
        if not city_key:
            return None

        forecast = self._provider_call("get_forecast", city_key, country_code=spec.country_code)
        if not forecast:
            return None
        periods = select_periods_for_target(forecast, spec.target_date, spec.horizon_hours)
        if not periods:
            return None
        use_precise_inputs = spec.target_date is not None or spec.market_type.startswith("monthly_")
        grid_data = None
        if use_precise_inputs:
            grid_data = self._provider_call("get_grid_data", city_key, country_code=spec.country_code)
        today = datetime.now(timezone.utc).date()
        days_out = 0
        if spec.target_date is not None:
            days_out = max(0, (spec.target_date - today).days)

        if spec.market_type == "monthly_precipitation":
            return self._monthly_precip_total_fair_value(spec, forecast, grid_data)

        if spec.market_type == "monthly_precip_days":
            return self._monthly_precip_days_fair_value(spec, forecast)

        if spec.market_type == "temperature":
            temperatures = extract_temperatures(periods)
            if not temperatures:
                return None

            if (not use_precise_inputs) and spec.contract_type in {"ge", "le"} and spec.threshold_high is None and self.kernel is not None:
                prob, conf = self.kernel.temperature_probability(
                    temperatures,
                    float(spec.threshold_low or 0.0),
                    above=(spec.contract_type == "ge"),
                )
                return WeatherFairValue(
                    fair_yes_prob=prob,
                    confidence=conf,
                    model="s02_forecast_only_kernel",
                    market_type=spec.market_type,
                    station_id=spec.station_id,
                    details={
                        "forecast_points": len(temperatures),
                        "station_label": spec.station_label,
                        "canonical_city": spec.canonical_city,
                        "city_query": spec.city,
                        "settlement_source": spec.settlement_source,
                        "settlement_location_id": spec.settlement_location_id,
                        "settlement_rounding": spec.settlement_rounding,
                        "source_count": 1,
                    },
                )

            grid_extreme_f = None
            grid_temp_values_f: List[float] = []
            if isinstance(grid_data, dict):
                temp_values_c = self._grid_values_for_target(grid_data, "temperature", spec.target_date, spec.horizon_hours)
                grid_temp_values_f = [float(c_to_f(v)) for v in temp_values_c if c_to_f(v) is not None]
                field_name = "maxTemperature" if spec.forecast_stat == "max" else "minTemperature"
                extreme_values_c = self._grid_values_for_target(grid_data, field_name, spec.target_date, spec.horizon_hours)
                extreme_values_f = [float(c_to_f(v)) for v in extreme_values_c if c_to_f(v) is not None]
                if extreme_values_f:
                    grid_extreme_f = max(extreme_values_f) if spec.forecast_stat == "max" else min(extreme_values_f)

            hourly_extreme = max(temperatures) if spec.forecast_stat == "max" else min(temperatures)
            observed_temp_f = None
            observation_details: Dict[str, Optional[float]] = {"noaa_observed_temp_f": None, "aviation_observed_temp_f": None}
            if use_precise_inputs:
                observed_temp_f, observation_details = self._current_observed_temp_f(spec)
            mu_candidates = [hourly_extreme]
            if grid_extreme_f is not None:
                mu_candidates.append(grid_extreme_f)
            if observed_temp_f is not None and spec.target_date == today:
                if spec.forecast_stat == "max":
                    mu_candidates.append(observed_temp_f)
                else:
                    mu_candidates.append(min(observed_temp_f, hourly_extreme))

            if spec.forecast_stat == "max":
                mu = sum(mu_candidates) / len(mu_candidates)
                if observed_temp_f is not None and spec.target_date == today:
                    mu = max(mu, observed_temp_f)
            else:
                mu = sum(mu_candidates) / len(mu_candidates)
                if grid_extreme_f is not None:
                    mu = min(mu, grid_extreme_f)
            temp_spread = (max(temperatures) - min(temperatures)) if len(temperatures) >= 2 else 0.0
            cross_model_spread = 0.0
            if grid_temp_values_f:
                series_extreme = max(grid_temp_values_f) if spec.forecast_stat == "max" else min(grid_temp_values_f)
                cross_model_spread = abs(series_extreme - hourly_extreme)
            sigma = max(1.15, 1.45 + (temp_spread * 0.14) + (cross_model_spread * 0.30) + (days_out * 0.40))
            contract = (spec.contract_type, float(spec.threshold_low or 0.0), spec.threshold_high)
            fair_yes = temperature_contract_probability(mu, sigma, contract)

            sample_score = min(1.0, math.sqrt(len(temperatures) / 24.0))
            margin = abs(fair_yes - 0.5)
            spread_penalty = min(1.0, temp_spread / 18.0)
            model_agreement = 1.0 - min(1.0, cross_model_spread / 8.0)
            obs_bonus = 0.10 if observed_temp_f is not None and spec.target_date == today else 0.0
            source_count = 1 + int(grid_extreme_f is not None) + int(observed_temp_f is not None)
            confidence = clamp(
                0.38
                + (0.20 * sample_score)
                + (0.18 * margin)
                + (0.16 * model_agreement)
                + (0.04 * min(3, source_count))
                + obs_bonus
                - (0.08 * spread_penalty)
                - (0.04 * days_out),
                0.35,
                0.97,
            )
            return WeatherFairValue(
                fair_yes_prob=fair_yes,
                confidence=confidence,
                model="s02_weather_engine_v4",
                market_type=spec.market_type,
                station_id=spec.station_id,
                details={
                    "mu": round(mu, 3),
                    "sigma": round(sigma, 3),
                    "temp_spread": round(temp_spread, 3),
                    "cross_model_spread": round(cross_model_spread, 3),
                    "forecast_points": len(temperatures),
                    "hourly_extreme_f": round(hourly_extreme, 3),
                    "grid_extreme_f": None if grid_extreme_f is None else round(float(grid_extreme_f), 3),
                    "observed_temp_f": None if observed_temp_f is None else round(float(observed_temp_f), 3),
                    **{k: (None if v is None else round(float(v), 3)) for k, v in observation_details.items()},
                    "station_label": spec.station_label,
                    "canonical_city": spec.canonical_city,
                    "city_query": spec.city,
                    "settlement_source": spec.settlement_source,
                    "settlement_location_id": spec.settlement_location_id,
                    "settlement_rounding": spec.settlement_rounding,
                    "source_count": source_count,
                },
            )

        pops: List[float] = []
        for period in periods:
            pop_obj = period.get("probabilityOfPrecipitation")
            value = 0.0
            if isinstance(pop_obj, dict):
                raw = pop_obj.get("value")
                if raw is not None:
                    try:
                        value = float(raw)
                    except Exception:
                            value = 0.0
            pops.append(value)
        if not pops:
            return None
        probs = [clamp(p / 100.0) for p in pops]
        pop_prob = sum(probs) / len(probs)

        qpf_inches = None
        snowfall_inches = None
        qpf_prob = None
        taf_prob = None
        if isinstance(grid_data, dict):
            qpf_values_mm = self._grid_values_for_target(grid_data, "quantitativePrecipitation", spec.target_date, spec.horizon_hours)
            snow_values_mm = self._grid_values_for_target(grid_data, "snowfallAmount", spec.target_date, spec.horizon_hours)
            if qpf_values_mm:
                qpf_inches = sum(mm_to_inches(v) or 0.0 for v in qpf_values_mm)
                scale = 0.02 if spec.precip_kind != "snow" else 0.04
                qpf_prob = clamp(1.0 - math.exp(-(qpf_inches / scale))) if qpf_inches is not None else None
            if snow_values_mm:
                snowfall_inches = sum(mm_to_inches(v) or 0.0 for v in snow_values_mm)
                if spec.precip_kind == "snow":
                    scale = 0.03
                    snowfall_prob = clamp(1.0 - math.exp(-(snowfall_inches / scale)))
                    qpf_prob = max(qpf_prob or 0.0, snowfall_prob)

        if use_precise_inputs and self.aviation_provider is not None and spec.station_id and hasattr(self.aviation_provider, "taf_precip_probability"):
            taf_prob = self.aviation_provider.taf_precip_probability(
                spec.station_id,
                target_date=spec.target_date,
                hours=spec.horizon_hours,
                precip_kind=spec.precip_kind,
            )

        weighted_terms: List[Tuple[float, float]] = [(pop_prob, 0.55)]
        if qpf_prob is not None:
            weighted_terms.append((qpf_prob, 0.25))
        if taf_prob is not None:
            weighted_terms.append((taf_prob, 0.20))
        total_weight = sum(weight for _, weight in weighted_terms)
        mean_prob = sum(prob * weight for prob, weight in weighted_terms) / total_weight
        spread_terms = [prob for prob, _ in weighted_terms]
        mean_sq = sum(prob * prob for prob in spread_terms) / len(spread_terms)
        variance = max(0.0, mean_sq - (sum(spread_terms) / len(spread_terms)) ** 2)
        sample_score = min(1.0, math.sqrt(len(probs) / 24.0))
        source_count = 1 + int(qpf_prob is not None) + int(taf_prob is not None)
        confidence = clamp(
            0.42
            + (0.16 * sample_score)
            + (0.16 * (1.0 - clamp(variance / 0.16)))
            + (0.05 * min(3, source_count))
            + (0.05 if qpf_inches is not None and qpf_inches > 0 else 0.0),
            0.35,
            0.93,
        )
        return WeatherFairValue(
            fair_yes_prob=mean_prob,
            confidence=confidence,
            model="s02_weather_engine_v4",
            market_type=spec.market_type,
            station_id=spec.station_id,
            details={
                "forecast_points": len(probs),
                "mean_pop": round(pop_prob, 3),
                "qpf_prob": None if qpf_prob is None else round(qpf_prob, 3),
                "taf_precip_prob": None if taf_prob is None else round(taf_prob, 3),
                "qpf_inches": None if qpf_inches is None else round(qpf_inches, 4),
                "snowfall_inches": None if snowfall_inches is None else round(snowfall_inches, 4),
                "precip_kind": spec.precip_kind,
                "variance": round(variance, 4),
                "station_label": spec.station_label,
                "canonical_city": spec.canonical_city,
                "city_query": spec.city,
                "settlement_source": spec.settlement_source,
                "settlement_location_id": spec.settlement_location_id,
                "settlement_rounding": spec.settlement_rounding,
                "source_count": source_count,
            },
        )
