"""NWS climate-product provider for daily CLI and month-to-date CF6 data."""
from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any, Dict, List, Optional

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

_PRODUCT_TTL = 900.0

_MONTHS = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}


def _parse_measure(token: str) -> Optional[float]:
    raw = str(token or "").strip().upper()
    if not raw or raw in {"M", "MM"}:
        return None
    if raw == "T":
        return 0.001
    raw = raw.rstrip("R")
    try:
        return float(raw)
    except Exception:
        return None


class NWSClimateProvider(BaseDataProvider):
    """Fetch and parse official NWS climate text products."""

    name = "nws_climate"
    BASE_URL = "https://api.weather.gov/products/types"

    def fetch(self, **kwargs: Any) -> Any:
        product = str(kwargs.get("product") or "cli").strip().lower()
        location_id = self.location_id_for(kwargs.get("location_id"), kwargs.get("station_id"))
        if not location_id:
            return None
        if product == "cf6":
            return self.get_cf6(location_id)
        return self.get_cli(location_id)

    @staticmethod
    def location_id_for(location_id: Any = None, station_id: Any = None) -> Optional[str]:
        location = str(location_id or "").strip().upper()
        if location:
            return location
        station = str(station_id or "").strip().upper()
        if station.startswith("K") and len(station) == 4:
            return station[1:]
        return station or None

    def _get_latest_product(self, product_type: str, location_id: str) -> Optional[Dict[str, Any]]:
        product_type = product_type.strip().upper()
        location_id = location_id.strip().upper()
        if not product_type or not location_id:
            return None
        cache_key = f"{product_type}:{location_id}"
        cached = self.get_cached(cache_key, ttl=_PRODUCT_TTL)
        if cached is not None:
            return cached
        url = f"{self.BASE_URL}/{product_type}/locations/{location_id}/latest"
        try:
            payload = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch %s product for %s", product_type, location_id)
            return None
        if not isinstance(payload, dict):
            return None
        self.set_cached(cache_key, payload)
        return payload

    def get_cli(self, location_id: str) -> Optional[Dict[str, Any]]:
        return self._get_latest_product("CLI", location_id)

    def get_cf6(self, location_id: str) -> Optional[Dict[str, Any]]:
        return self._get_latest_product("CF6", location_id)

    def parse_cli(self, product_text: str) -> Optional[Dict[str, Any]]:
        text = str(product_text or "")
        if not text:
            return None
        date_match = re.search(r"CLIMATE SUMMARY FOR ([A-Z]+)\s+(\d{1,2})\s+(\d{4})", text, re.IGNORECASE)
        if not date_match:
            return None
        month = _MONTHS.get(date_match.group(1).upper())
        if month is None:
            return None
        report_date = date(int(date_match.group(3)), month, int(date_match.group(2)))

        precip_section_match = re.search(
            r"PRECIPITATION \(IN\)(.*?)(?:SNOWFALL \(IN\)|DEGREE DAYS|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        snow_section_match = re.search(
            r"SNOWFALL \(IN\)(.*?)(?:DEGREE DAYS|WIND \(MPH\)|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        precip_section = precip_section_match.group(1) if precip_section_match else ""
        snow_section = snow_section_match.group(1) if snow_section_match else ""

        max_match = re.search(r"^\s*MAXIMUM\s+(-?\d+(?:\.\d+)?)(?:[A-Z])?", text, re.MULTILINE)
        min_match = re.search(r"^\s*MINIMUM\s+(-?\d+(?:\.\d+)?)(?:[A-Z])?", text, re.MULTILINE)
        yesterday_precip_match = re.search(r"^\s*YESTERDAY\s+([0-9.TM]+)", precip_section, re.MULTILINE)
        month_precip_match = re.search(r"^\s*MONTH TO DATE\s+([0-9.TM]+)", precip_section, re.MULTILINE)
        yesterday_snow_match = re.search(r"^\s*YESTERDAY\s+([0-9.TM]+)", snow_section, re.MULTILINE)
        month_snow_match = re.search(r"^\s*MONTH TO DATE\s+([0-9.TM]+)", snow_section, re.MULTILINE)

        return {
            "report_date": report_date.isoformat(),
            "max_temp_f": None if not max_match else float(max_match.group(1)),
            "min_temp_f": None if not min_match else float(min_match.group(1)),
            "yesterday_precip_in": None if not yesterday_precip_match else _parse_measure(yesterday_precip_match.group(1)),
            "month_to_date_precip_in": None if not month_precip_match else _parse_measure(month_precip_match.group(1)),
            "yesterday_snow_in": None if not yesterday_snow_match else _parse_measure(yesterday_snow_match.group(1)),
            "month_to_date_snow_in": None if not month_snow_match else _parse_measure(month_snow_match.group(1)),
        }

    def parse_cf6(self, product_text: str) -> Optional[Dict[str, Any]]:
        text = str(product_text or "")
        if not text:
            return None
        month_match = re.search(r"MONTH:\s+([A-Z]+)", text)
        year_match = re.search(r"YEAR:\s+(\d{4})", text)
        if not month_match or not year_match:
            return None
        month_name = month_match.group(1).upper()
        month = _MONTHS.get(month_name)
        if month is None:
            return None
        year = int(year_match.group(1))

        rows: List[Dict[str, Any]] = []
        for line in text.splitlines():
            match = re.match(
                r"^\s*(\d{1,2})\s+(-?\d+|M)\s+(-?\d+|M)\s+(-?\d+|M)\s+(-?\d+|M)\s+(-?\d+|M)\s+(-?\d+|M)\s+([0-9.TM]+)\s+([0-9.TM]+)",
                line,
            )
            if not match:
                continue
            day = int(match.group(1))
            rows.append(
                {
                    "day": day,
                    "date": date(year, month, day).isoformat(),
                    "max_temp_f": _parse_measure(match.group(2)),
                    "min_temp_f": _parse_measure(match.group(3)),
                    "precip_in": _parse_measure(match.group(8)),
                    "snow_in": _parse_measure(match.group(9)),
                }
            )

        precip_days_match = re.search(r"0\.01 INCH OR MORE:\s+(\d+)", text)
        total_precip_match = re.search(r"TOTAL FOR MONTH:\s+([0-9.TM]+)", text)
        total_snow_match = re.search(r"TOTAL MONTH:\s+([0-9.TM]+)", text)
        return {
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "rows": rows,
            "precip_days": int(precip_days_match.group(1)) if precip_days_match else sum(
                1 for row in rows if (row.get("precip_in") or 0.0) > 0.0
            ),
            "month_to_date_precip_in": None if not total_precip_match else _parse_measure(total_precip_match.group(1)),
            "month_to_date_snow_in": None if not total_snow_match else _parse_measure(total_snow_match.group(1)),
        }

    def get_daily_summary(self, location_id: str) -> Optional[Dict[str, Any]]:
        product = self.get_cli(location_id)
        if not product:
            return None
        return self.parse_cli(str(product.get("productText") or ""))

    def get_month_to_date_summary(
        self,
        location_id: str,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        product = self.get_cf6(location_id)
        if not product:
            return None
        parsed = self.parse_cf6(str(product.get("productText") or ""))
        if not parsed:
            return None
        if target_year is not None and int(parsed["year"]) != int(target_year):
            return None
        if target_month is not None and int(parsed["month"]) != int(target_month):
            return None

        rows = list(parsed.get("rows") or [])
        return {
            "location_id": location_id.strip().upper(),
            "year": int(parsed["year"]),
            "month": int(parsed["month"]),
            "precip_in": float(parsed.get("month_to_date_precip_in") or 0.0),
            "snow_in": float(parsed.get("month_to_date_snow_in") or 0.0),
            "precip_days": int(parsed.get("precip_days") or 0),
            "rows": rows,
            "last_reported_day": max((int(row["day"]) for row in rows), default=0),
        }
