"""Global climate provider backed by NASA GISTEMP and Berkeley Earth monthly updates."""
from __future__ import annotations

import math
import re
from html import unescape
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_text

_SERIES_TTL = 6 * 3600.0
_MONTH_UPDATE_TTL = 6 * 3600.0
_NASA_GISTEMP_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.txt"
_BERKELEY_URL_TEMPLATE = "https://berkeleyearth.org/{slug}/"
_MONTH_NAMES = {
    1: "january",
    2: "february",
    3: "march",
    4: "april",
    5: "may",
    6: "june",
    7: "july",
    8: "august",
    9: "september",
    10: "october",
    11: "november",
    12: "december",
}
_ORDINAL_RANK = {
    "warmest": 1,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def _month_distance(year_a: int, month_a: int, year_b: int, month_b: int) -> int:
    return ((year_b - year_a) * 12) + (month_b - month_a)


def _safe_mean(values: List[float]) -> Optional[float]:
    return mean(values) if values else None


def _safe_pstdev(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(pstdev(values))


def _extract_paragraphs(html_text: str) -> List[str]:
    paragraphs: List[str] = []
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", str(html_text or ""), re.IGNORECASE | re.DOTALL):
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _berkeley_slug(year: int, month: int) -> Optional[str]:
    month_name = _MONTH_NAMES.get(int(month))
    if month_name is None:
        return None
    return f"{month_name}-{int(year)}-temperature-update"


class GlobalClimateProvider(BaseDataProvider):
    """Fetch monthly global land-ocean anomaly series and derive simple month-level nowcasts."""

    name = "global_climate"

    def fetch(self, **kwargs: Any) -> Any:
        year = kwargs.get("year")
        month = kwargs.get("month")
        if year and month:
            return self.estimate_monthly_anomaly(int(year), int(month))
        return self.get_monthly_series()

    @staticmethod
    def parse_nasa_monthly_series(text: str) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        latest: Optional[Tuple[int, int]] = None
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if not re.match(r"^\d{4}\b", stripped):
                continue
            tokens = stripped.split()
            if len(tokens) < 13:
                continue
            year = int(tokens[0])
            for month in range(1, 13):
                raw = tokens[month].strip()
                if raw == "****":
                    continue
                try:
                    value_c = float(raw) / 100.0
                except Exception:
                    continue
                rows.append(
                    {
                        "year": year,
                        "month": month,
                        "anomaly_c": value_c,
                    }
                )
                if latest is None or (year, month) > latest:
                    latest = (year, month)
        rows.sort(key=lambda item: (int(item["year"]), int(item["month"])))
        return {
            "rows": rows,
            "latest_year": None if latest is None else latest[0],
            "latest_month": None if latest is None else latest[1],
            "source_url": _NASA_GISTEMP_URL,
        }

    def get_monthly_series(self) -> Optional[Dict[str, Any]]:
        cached = self.get_cached("nasa_gistemp_series", ttl=_SERIES_TTL)
        if cached is not None:
            return cached
        try:
            text = http_get_text(_NASA_GISTEMP_URL)
        except Exception:
            self.logger.warning("Failed to fetch NASA GISTEMP monthly table")
            return None
        parsed = self.parse_nasa_monthly_series(text)
        if not parsed.get("rows"):
            return None
        self.set_cached("nasa_gistemp_series", parsed)
        return parsed

    @staticmethod
    def parse_berkeley_monthly_update(html_text: str, year: int, month: int) -> Optional[Dict[str, Any]]:
        month_name = _MONTH_NAMES.get(int(month))
        if month_name is None:
            return None
        label = f"{month_name.title()} {int(year)}"
        paragraphs = _extract_paragraphs(html_text)
        if not paragraphs:
            return None

        summary_paragraph = None
        for paragraph in paragraphs[:8]:
            if label.lower() not in paragraph.lower():
                continue
            if "°c" not in paragraph.lower():
                continue
            if "global average" in paragraph.lower() or "was measured as" in paragraph.lower():
                summary_paragraph = paragraph
                break
        if summary_paragraph is None:
            return None

        value_match = re.search(
            rf"(?:Globally,\s*)?{re.escape(label)}.*?(?:was measured as|with a monthly global average of)\s*([0-9.]+)\s*(?:±|\+/-)\s*([0-9.]+)\s*°C",
            summary_paragraph,
            re.IGNORECASE,
        )
        if not value_match:
            return None

        anomaly_c = float(value_match.group(1))
        uncertainty_c = float(value_match.group(2))
        rank = None
        rank_match = re.search(r"\b(?:was the|is the)\s+([a-z]+)\s+warmest\b", summary_paragraph, re.IGNORECASE)
        if rank_match:
            rank = _ORDINAL_RANK.get(rank_match.group(1).lower())
        if rank is None and re.search(r"\bwarmest\b", summary_paragraph, re.IGNORECASE):
            rank = 1
        return {
            "year": int(year),
            "month": int(month),
            "anomaly_c": anomaly_c,
            "uncertainty_c": uncertainty_c,
            "rank": rank,
            "is_record": rank == 1,
            "summary": summary_paragraph,
            "source_url": _BERKELEY_URL_TEMPLATE.format(slug=_berkeley_slug(year, month)),
        }

    def get_berkeley_monthly_update(self, year: int, month: int) -> Optional[Dict[str, Any]]:
        slug = _berkeley_slug(year, month)
        if slug is None:
            return None
        cache_key = f"berkeley:{year:04d}-{month:02d}"
        cached = self.get_cached(cache_key, ttl=_MONTH_UPDATE_TTL)
        if cached is not None:
            return cached
        url = _BERKELEY_URL_TEMPLATE.format(slug=slug)
        try:
            html_text = http_get_text(url)
        except Exception:
            return None
        parsed = self.parse_berkeley_monthly_update(html_text, year=year, month=month)
        if parsed is None:
            return None
        self.set_cached(cache_key, parsed)
        return parsed

    def month_value(self, year: int, month: int) -> Optional[float]:
        series = self.get_monthly_series()
        if not series:
            return None
        for row in series["rows"]:
            if int(row["year"]) == int(year) and int(row["month"]) == int(month):
                return float(row["anomaly_c"])
        return None

    def record_threshold_c(self, year: int, month: int) -> Optional[float]:
        series = self.get_monthly_series()
        if not series:
            return None
        values = [
            float(row["anomaly_c"])
            for row in series["rows"]
            if int(row["month"]) == int(month) and int(row["year"]) < int(year)
        ]
        return max(values) if values else None

    def estimate_monthly_anomaly(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        year = int(target_year if target_year is not None else year or 0)
        month = int(target_month if target_month is not None else month or 0)
        if year <= 0 or month <= 0:
            return None
        series = self.get_monthly_series()
        if not series:
            return None

        latest_year = series.get("latest_year")
        latest_month = series.get("latest_month")
        if latest_year is None or latest_month is None:
            return None

        rows = [
            (int(row["year"]), int(row["month"]), float(row["anomaly_c"]))
            for row in series["rows"]
        ]
        by_key = {(row_year, row_month): value for row_year, row_month, value in rows}
        latest_value = by_key.get((int(latest_year), int(latest_month)))
        actual = by_key.get((int(year), int(month)))
        latest_berkeley = self.get_berkeley_monthly_update(int(latest_year), int(latest_month))
        berkeley_update = self.get_berkeley_monthly_update(int(year), int(month))
        months_ahead = max(0, _month_distance(int(latest_year), int(latest_month), int(year), int(month)))

        nasa_published = actual is not None and (int(year), int(month)) <= (int(latest_year), int(latest_month))
        berkeley_published = isinstance(berkeley_update, dict)

        actual_values = []
        if nasa_published:
            actual_values.append(float(actual))
        if berkeley_published:
            actual_values.append(float(berkeley_update["anomaly_c"]))

        if actual_values:
            actual_mu = float(mean(actual_values))
            actual_sigma = max(0.01, 0.5 * _safe_pstdev(actual_values) + 0.01)
            if nasa_published and berkeley_published:
                release_state = "published_dual_source"
            elif nasa_published:
                release_state = "published_nasa_only"
            else:
                release_state = "published_berkeley_only"
            return {
                "mu_c": round(actual_mu, 4),
                "sigma_c": round(actual_sigma, 4),
                "actual_c": round(actual_mu, 4),
                "nasa_actual_c": None if actual is None else round(float(actual), 4),
                "berkeley_actual_c": None if not berkeley_published else round(float(berkeley_update["anomaly_c"]), 4),
                "is_published": True,
                "latest_year": int(latest_year),
                "latest_month": int(latest_month),
                "source_url": _NASA_GISTEMP_URL,
                "berkeley_source_url": None if not berkeley_published else berkeley_update["source_url"],
                "source_count": len(actual_values),
                "confidence": 0.995 if len(actual_values) >= 2 else 0.99,
                "berkeley_rank": None if not berkeley_published else berkeley_update.get("rank"),
                "nasa_published": nasa_published,
                "berkeley_published": berkeley_published,
                "months_ahead": months_ahead,
                "release_state": release_state,
            }

        same_month_history = [value for row_year, row_month, value in rows if row_month == int(month) and row_year < int(year)]
        trailing_rows = [(row_year, row_month, value) for row_year, row_month, value in rows if (row_year, row_month) < (int(year), int(month))]
        if not same_month_history or not trailing_rows:
            return None

        same_recent = same_month_history[-10:]
        recent_values = [value for _, _, value in trailing_rows[-12:]]
        recent_short = recent_values[-3:] or recent_values
        season_mean = _safe_mean(same_recent)
        trend_anchor = _safe_mean(recent_short)
        recent_mean = _safe_mean(recent_values[-6:] or recent_values)
        long_recent = _safe_mean(recent_values)
        if season_mean is None or trend_anchor is None or recent_mean is None or long_recent is None:
            return None

        warming_bias = recent_mean - long_recent
        momentum_bias = trend_anchor - recent_mean
        mu_c = season_mean + (0.55 * warming_bias) + (0.30 * momentum_bias)
        latest_anchor_values = []
        if latest_value is not None:
            latest_anchor_values.append(float(latest_value))
        if isinstance(latest_berkeley, dict):
            latest_anchor_values.append(float(latest_berkeley["anomaly_c"]))
        latest_anchor = _safe_mean(latest_anchor_values)
        if latest_anchor is not None:
            mu_c = (0.65 * mu_c) + (0.35 * float(latest_anchor))

        season_sigma = _safe_pstdev(same_recent)
        recent_sigma = _safe_pstdev(recent_values[-6:] or recent_values)
        sigma_c = max(0.04, (0.70 * max(0.04, season_sigma)) + (0.30 * max(0.03, recent_sigma)) + (0.02 * months_ahead))

        agreement_penalty = min(0.12, abs(mu_c - season_mean))
        confidence = max(
            0.28,
            min(
                0.76,
                0.34
                + (0.12 * min(1.0, len(same_recent) / 10.0))
                + (0.12 * min(1.0, len(recent_values) / 12.0))
                + (0.05 if isinstance(latest_berkeley, dict) else 0.0)
                - (0.05 * months_ahead)
                - agreement_penalty,
            ),
        )
        anchor_source_count = len(latest_anchor_values)
        release_state = "nowcast_dual_anchor" if anchor_source_count >= 2 else "nowcast_nasa_anchor"
        return {
            "mu_c": round(mu_c, 4),
            "sigma_c": round(sigma_c, 4),
            "actual_c": None if actual is None else round(float(actual), 4),
            "is_published": False,
            "latest_year": int(latest_year),
            "latest_month": int(latest_month),
            "latest_nasa_c": None if latest_value is None else round(float(latest_value), 4),
            "latest_berkeley_c": None if not isinstance(latest_berkeley, dict) else round(float(latest_berkeley["anomaly_c"]), 4),
            "same_month_mean_c": round(season_mean, 4),
            "same_month_sigma_c": round(season_sigma, 4),
            "recent_mean_c": round(recent_mean, 4),
            "recent_short_mean_c": round(trend_anchor, 4),
            "warming_bias_c": round(warming_bias, 4),
            "momentum_bias_c": round(momentum_bias, 4),
            "months_ahead": months_ahead,
            "source_url": _NASA_GISTEMP_URL,
            "berkeley_source_url": None if not isinstance(latest_berkeley, dict) else latest_berkeley["source_url"],
            "source_count": 1 + int(isinstance(latest_berkeley, dict)),
            "anchor_source_count": anchor_source_count,
            "nasa_published": nasa_published,
            "berkeley_published": berkeley_published,
            "release_state": release_state,
            "confidence": round(confidence, 4),
        }
