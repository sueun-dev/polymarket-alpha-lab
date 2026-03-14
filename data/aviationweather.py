"""Official Aviation Weather Center data provider for METAR/TAF products."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

_METAR_TTL = 300.0
_TAF_TTL = 900.0


class AviationWeatherProvider(BaseDataProvider):
    """Fetch decoded METAR and TAF data from the Aviation Weather Center API."""

    name = "aviation_weather"
    BASE_URL = "https://aviationweather.gov/api/data"

    def fetch(self, **kwargs: Any) -> Any:
        station_id = str(kwargs.get("station_id") or kwargs.get("station") or "").strip().upper()
        product = str(kwargs.get("product") or "metar").strip().lower()
        if not station_id:
            return None
        if product == "taf":
            return self.get_taf(station_id)
        return self.get_metar(station_id)

    def get_metar(self, station_id: str) -> Optional[Dict[str, Any]]:
        station_id = station_id.strip().upper()
        if not station_id:
            return None
        cache_key = f"metar:{station_id}"
        cached = self.get_cached(cache_key, ttl=_METAR_TTL)
        if cached is not None:
            return cached
        url = f"{self.BASE_URL}/metar?ids={station_id}&format=json"
        try:
            payload = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch METAR for %s", station_id)
            return None
        if not isinstance(payload, list) or not payload:
            return None
        first = payload[0]
        if not isinstance(first, dict):
            return None
        self.set_cached(cache_key, first)
        return first

    def get_taf(self, station_id: str) -> Optional[Dict[str, Any]]:
        station_id = station_id.strip().upper()
        if not station_id:
            return None
        cache_key = f"taf:{station_id}"
        cached = self.get_cached(cache_key, ttl=_TAF_TTL)
        if cached is not None:
            return cached
        url = f"{self.BASE_URL}/taf?ids={station_id}&format=json"
        try:
            payload = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch TAF for %s", station_id)
            return None
        if not isinstance(payload, list) or not payload:
            return None
        first = payload[0]
        if not isinstance(first, dict):
            return None
        self.set_cached(cache_key, first)
        return first

    def latest_temperature_f(self, station_id: str) -> Optional[float]:
        metar = self.get_metar(station_id)
        if not isinstance(metar, dict):
            return None
        temp_c = metar.get("temp")
        if temp_c is None:
            return None
        try:
            return (float(temp_c) * 9.0 / 5.0) + 32.0
        except Exception:
            return None

    def taf_precip_probability(
        self,
        station_id: str,
        target_date: Optional[date] = None,
        hours: int = 24,
        precip_kind: str = "any",
    ) -> Optional[float]:
        """Approximate event probability from overlapping TAF segments."""
        taf = self.get_taf(station_id)
        if not isinstance(taf, dict):
            return None
        fcsts = taf.get("fcsts")
        if not isinstance(fcsts, list) or not fcsts:
            return None

        start_ts = int(datetime.now(timezone.utc).timestamp())
        end_ts = start_ts + (max(1, hours) * 3600)
        if target_date is not None:
            start_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
            end_dt = start_dt.replace(hour=23, minute=59, second=59)
            start_ts = int(start_dt.timestamp())
            end_ts = int(end_dt.timestamp())

        probs: List[float] = []
        for segment in fcsts:
            if not isinstance(segment, dict):
                continue
            seg_start = self._to_int(segment.get("timeFrom"))
            seg_end = self._to_int(segment.get("timeTo"))
            if seg_start is None or seg_end is None or seg_end <= start_ts or seg_start >= end_ts:
                continue
            prob = self._segment_precip_probability(segment, precip_kind=precip_kind)
            if prob is None or prob <= 0:
                continue
            overlap_start = max(start_ts, seg_start)
            overlap_end = min(end_ts, seg_end)
            overlap_hours = max(1.0, (overlap_end - overlap_start) / 3600.0)
            duration_hours = max(1.0, (seg_end - seg_start) / 3600.0)
            weight = min(1.0, overlap_hours / duration_hours)
            probs.append(min(1.0, prob * weight))

        if not probs:
            return None
        complement = 1.0
        for prob in probs:
            complement *= (1.0 - max(0.0, min(1.0, prob)))
        return 1.0 - complement

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _contains_precip(wx_string: str, precip_kind: str) -> bool:
        wx = str(wx_string).upper()
        if precip_kind == "snow":
            return any(token in wx for token in ["SN", "SHSN", "BLSN"])
        if precip_kind == "rain":
            return any(token in wx for token in ["RA", "DZ", "SHRA", "TSRA", "FZRA"])
        return any(token in wx for token in ["RA", "DZ", "SN", "SHRA", "SHSN", "TSRA", "FZRA"])

    def _segment_precip_probability(self, segment: Dict[str, Any], precip_kind: str) -> Optional[float]:
        wx_string = str(segment.get("wxString") or "").strip()
        if not wx_string or not self._contains_precip(wx_string, precip_kind=precip_kind):
            return None

        explicit = segment.get("probability")
        if explicit is not None:
            try:
                return max(0.0, min(1.0, float(explicit) / 100.0))
            except Exception:
                pass

        fcst_change = str(segment.get("fcstChange") or "").strip().upper()
        visib = segment.get("visib")
        vis_penalty = 0.0
        try:
            vis_value = float(str(visib).replace("+", ""))
            if vis_value <= 2.0:
                vis_penalty = 0.10
        except Exception:
            vis_penalty = 0.0

        if fcst_change.startswith("PROB"):
            digits = "".join(ch for ch in fcst_change if ch.isdigit())
            if digits:
                return max(0.0, min(1.0, float(digits) / 100.0))
            return 0.35
        if fcst_change == "TEMPO":
            return min(0.70, 0.45 + vis_penalty)
        if fcst_change == "BECMG":
            return 0.40
        # Prevailing and FM groups imply the forecast office expects precip.
        return min(0.85, 0.62 + vis_penalty)
