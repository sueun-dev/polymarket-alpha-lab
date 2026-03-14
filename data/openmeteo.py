"""Global weather provider using the official Open-Meteo APIs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

_GEO_TTL = 86400.0
_FORECAST_TTL = 1800.0


class OpenMeteoProvider(BaseDataProvider):
    """Global forecast provider for cities outside the NOAA coverage map."""

    name = "open_meteo"
    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def fetch(self, **kwargs: Any) -> Any:
        city = str(kwargs.get("city") or "").strip()
        if not city:
            return None
        return self.get_forecast(city, country_code=kwargs.get("country_code"))

    def geocode(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        city = str(city or "").strip()
        if not city:
            return None
        cache_key = f"geo:{city.lower()}:{(country_code or '').lower()}"
        cached = self.get_cached(cache_key, ttl=_GEO_TTL)
        if cached is not None:
            return cached

        params = {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        }
        if country_code:
            params["countryCode"] = str(country_code).upper()
        url = f"{self.GEO_URL}?{urlencode(params)}"
        try:
            payload = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to geocode %s", city)
            return None
        if not isinstance(payload, dict):
            return None
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        if not isinstance(first, dict):
            return None
        self.set_cached(cache_key, first)
        return first

    def city_profile(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        geo = self.geocode(city, country_code=country_code)
        if not isinstance(geo, dict):
            return None
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is None or lon is None:
            return None
        canonical = str(geo.get("name") or city).strip().lower()
        return {
            "canonical": canonical,
            "coords": (float(lat), float(lon)),
            "station_id": None,
            "station_label": str(geo.get("name") or city).strip() or None,
            "climate_location_id": None,
            "country_code": str(geo.get("country_code") or "").strip().lower() or None,
            "forecast_source": self.name,
        }

    def normalize_city(self, city: str, country_code: Optional[str] = None) -> Optional[str]:
        profile = self.city_profile(city, country_code=country_code)
        if profile is None:
            return None
        return str(profile.get("canonical") or "").strip() or None

    def _get_payload(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        geo = self.geocode(city, country_code=country_code)
        if not isinstance(geo, dict):
            return None
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is None or lon is None:
            return None
        cache_key = f"forecast:{city.lower()}:{geo.get('latitude')}:{geo.get('longitude')}"
        cached = self.get_cached(cache_key, ttl=_FORECAST_TTL)
        if cached is not None:
            return cached

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "precipitation_probability",
                    "precipitation",
                    "snowfall",
                ]
            ),
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "snowfall_sum",
                    "precipitation_probability_max",
                ]
            ),
            "current": "temperature_2m",
            "timezone": "UTC",
            "forecast_days": 16,
        }
        url = f"{self.FORECAST_URL}?{urlencode(params)}"
        try:
            payload = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch Open-Meteo forecast for %s", city)
            return None
        if not isinstance(payload, dict):
            return None
        payload["_geo"] = geo
        self.set_cached(cache_key, payload)
        return payload

    def get_forecast(self, city: str, country_code: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        payload = self._get_payload(city, country_code=country_code)
        if not isinstance(payload, dict):
            return None
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            return None
        times = hourly.get("time")
        temps = hourly.get("temperature_2m")
        pops = hourly.get("precipitation_probability")
        precips = hourly.get("precipitation")
        snows = hourly.get("snowfall")
        if not isinstance(times, list) or not isinstance(temps, list):
            return None

        periods: List[Dict[str, Any]] = []
        for idx, ts in enumerate(times):
            try:
                start_dt = datetime.fromisoformat(f"{ts}+00:00" if "T" in str(ts) and "+" not in str(ts) else str(ts))
            except Exception:
                continue
            end_dt = datetime.fromtimestamp(start_dt.timestamp() + 3600, tz=start_dt.tzinfo or timezone.utc)
            temp = temps[idx] if idx < len(temps) else None
            pop = pops[idx] if isinstance(pops, list) and idx < len(pops) else None
            precip = precips[idx] if isinstance(precips, list) and idx < len(precips) else None
            snow = snows[idx] if isinstance(snows, list) and idx < len(snows) else None
            periods.append(
                {
                    "startTime": start_dt.isoformat(),
                    "endTime": end_dt.isoformat(),
                    "temperature": temp,
                    "temperatureUnit": "C",
                    "probabilityOfPrecipitation": {"value": pop},
                    "precipitation": precip,
                    "snowfall": snow,
                }
            )
        return periods

    def get_hourly_periods(self, city: str, country_code: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        return self.get_forecast(city, country_code=country_code)

    def get_daily_summary(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        payload = self._get_payload(city, country_code=country_code)
        if not isinstance(payload, dict):
            return None
        daily = payload.get("daily")
        if not isinstance(daily, dict):
            return None
        return daily

    def get_grid_data(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        payload = self._get_payload(city, country_code=country_code)
        if not isinstance(payload, dict):
            return None
        hourly = payload.get("hourly")
        daily = payload.get("daily")
        if not isinstance(hourly, dict) or not isinstance(daily, dict):
            return None

        hourly_times = hourly.get("time") or []
        daily_times = daily.get("time") or []
        if not isinstance(hourly_times, list) or not isinstance(daily_times, list):
            return None

        def _hourly_values(field: str) -> List[Dict[str, Any]]:
            raw_values = hourly.get(field)
            if not isinstance(raw_values, list):
                return []
            rows: List[Dict[str, Any]] = []
            for idx, ts in enumerate(hourly_times):
                if idx >= len(raw_values):
                    break
                value = raw_values[idx]
                if value is None:
                    continue
                rows.append({"validTime": f"{ts}+00:00/PT1H", "value": value})
            return rows

        def _daily_values(field: str) -> List[Dict[str, Any]]:
            raw_values = daily.get(field)
            if not isinstance(raw_values, list):
                return []
            rows: List[Dict[str, Any]] = []
            for idx, ts in enumerate(daily_times):
                if idx >= len(raw_values):
                    break
                value = raw_values[idx]
                if value is None:
                    continue
                rows.append({"validTime": f"{ts}T00:00:00+00:00/PT24H", "value": value})
            return rows

        return {
            "temperature": {"uom": "wmoUnit:degC", "values": _hourly_values("temperature_2m")},
            "maxTemperature": {"uom": "wmoUnit:degC", "values": _daily_values("temperature_2m_max")},
            "minTemperature": {"uom": "wmoUnit:degC", "values": _daily_values("temperature_2m_min")},
            "probabilityOfPrecipitation": {"uom": "wmoUnit:percent", "values": _hourly_values("precipitation_probability")},
            "quantitativePrecipitation": {"uom": "wmoUnit:mm", "values": _hourly_values("precipitation")},
            "snowfallAmount": {"uom": "wmoUnit:mm", "values": _hourly_values("snowfall")},
        }

    def get_latest_observation(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        payload = self._get_payload(city, country_code=country_code)
        if not isinstance(payload, dict):
            return None
        current = payload.get("current")
        geo = payload.get("_geo")
        if not isinstance(current, dict) or not isinstance(geo, dict):
            return None
        raw_temp = current.get("temperature_2m")
        if raw_temp is None:
            return None
        try:
            temperature_c = float(raw_temp)
        except Exception:
            return None
        return {
            "city": str(geo.get("name") or city).strip().lower(),
            "station_id": None,
            "station_label": str(geo.get("name") or city).strip() or None,
            "timestamp": current.get("time"),
            "temperature_c": temperature_c,
            "temperature_f": (temperature_c * 9.0 / 5.0) + 32.0,
        }
