"""NOAA Weather data provider using the free api.weather.gov API."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

# Cache TTL constants (seconds)
_GRID_TTL = 86400.0  # 24 hours
_FORECAST_TTL = 3600.0  # 1 hour
_OBS_TTL = 600.0  # 10 minutes
_GRID_DATA_TTL = 3600.0  # 1 hour


class NOAAWeatherProvider(BaseDataProvider):
    """Fetches weather forecasts from the NOAA api.weather.gov service.

    Uses a two-step lookup:
    1. ``/points/{lat},{lon}`` to obtain the forecast grid office and coordinates.
    2. ``/gridpoints/{office}/{gridX},{gridY}/forecast/hourly`` for hourly data.

    No API key is required.
    """

    name = "noaa_weather"

    CITY_PROFILES: Dict[str, Dict[str, Any]] = {
        "new york": {
            "canonical": "new york",
            "coords": (40.7128, -74.0060),
            "station_id": "KLGA",
            "station_label": "LaGuardia Airport",
            "climate_location_id": "LGA",
        },
        "nyc": {
            "canonical": "new york",
            "coords": (40.7128, -74.0060),
            "station_id": "KLGA",
            "station_label": "LaGuardia Airport",
            "climate_location_id": "LGA",
        },
        "chicago": {
            "canonical": "chicago",
            "coords": (41.8781, -87.6298),
            "station_id": "KORD",
            "station_label": "Chicago O'Hare",
            "climate_location_id": "ORD",
        },
        "miami": {
            "canonical": "miami",
            "coords": (25.7617, -80.1918),
            "station_id": "KMIA",
            "station_label": "Miami International Airport",
            "climate_location_id": "MIA",
        },
        "los angeles": {
            "canonical": "los angeles",
            "coords": (34.0522, -118.2437),
            "station_id": "KLAX",
            "station_label": "Los Angeles International Airport",
            "climate_location_id": "LAX",
        },
        "la": {
            "canonical": "los angeles",
            "coords": (34.0522, -118.2437),
            "station_id": "KLAX",
            "station_label": "Los Angeles International Airport",
            "climate_location_id": "LAX",
        },
        "washington dc": {
            "canonical": "washington dc",
            "coords": (38.9072, -77.0369),
            "station_id": "KDCA",
            "station_label": "Reagan National Airport",
            "climate_location_id": "DCA",
        },
        "dc": {
            "canonical": "washington dc",
            "coords": (38.9072, -77.0369),
            "station_id": "KDCA",
            "station_label": "Reagan National Airport",
            "climate_location_id": "DCA",
        },
        "houston": {
            "canonical": "houston",
            "coords": (29.7604, -95.3698),
            "station_id": "KIAH",
            "station_label": "Houston Intercontinental Airport",
            "climate_location_id": "IAH",
        },
        "phoenix": {
            "canonical": "phoenix",
            "coords": (33.4484, -112.0740),
            "station_id": "KPHX",
            "station_label": "Phoenix Sky Harbor",
            "climate_location_id": "PHX",
        },
        "philadelphia": {
            "canonical": "philadelphia",
            "coords": (39.9526, -75.1652),
            "station_id": "KPHL",
            "station_label": "Philadelphia International Airport",
            "climate_location_id": "PHL",
        },
        "san francisco": {
            "canonical": "san francisco",
            "coords": (37.7749, -122.4194),
            "station_id": "KSFO",
            "station_label": "San Francisco International Airport",
            "climate_location_id": "SFO",
        },
        "sf": {
            "canonical": "san francisco",
            "coords": (37.7749, -122.4194),
            "station_id": "KSFO",
            "station_label": "San Francisco International Airport",
            "climate_location_id": "SFO",
        },
        "seattle": {
            "canonical": "seattle",
            "coords": (47.6062, -122.3321),
            "station_id": "KSEA",
            "station_label": "Seattle-Tacoma International Airport",
            "climate_location_id": "SEA",
        },
        "denver": {
            "canonical": "denver",
            "coords": (39.7392, -104.9903),
            "station_id": "KDEN",
            "station_label": "Denver International Airport",
            "climate_location_id": "DEN",
        },
        "boston": {
            "canonical": "boston",
            "coords": (42.3601, -71.0589),
            "station_id": "KBOS",
            "station_label": "Boston Logan Airport",
            "climate_location_id": "BOS",
        },
        "atlanta": {
            "canonical": "atlanta",
            "coords": (33.7490, -84.3880),
            "station_id": "KATL",
            "station_label": "Hartsfield-Jackson Atlanta",
            "climate_location_id": "ATL",
        },
        "dallas": {
            "canonical": "dallas",
            "coords": (32.7767, -96.7970),
            "station_id": "KDAL",
            "station_label": "Dallas Love Field",
            "climate_location_id": "DAL",
        },
        "las vegas": {
            "canonical": "las vegas",
            "coords": (36.1699, -115.1398),
            "station_id": "KLAS",
            "station_label": "Harry Reid International Airport",
            "climate_location_id": "LAS",
        },
    }
    CITY_COORDS: Dict[str, tuple[float, float]] = {
        name: tuple(profile["coords"]) for name, profile in CITY_PROFILES.items()
    }

    # Pre-sorted city names longest-first so that "los angeles" matches before
    # "la", "new york" before "nyc", etc.
    _SORTED_CITY_NAMES: List[str] = sorted(CITY_COORDS.keys(), key=len, reverse=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, **kwargs: Any) -> Any:
        """Main entry point.  Delegates to :meth:`get_forecast`.

        Accepted keyword arguments:
        * ``city`` -- city name to look up.
        """
        city: Optional[str] = kwargs.get("city")
        if not city:
            return None
        return self.get_forecast(city, country_code=kwargs.get("country_code"))

    def city_profile(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return normalised metadata for *city* or *None* if unsupported."""
        if not city:
            return None
        profile = self.CITY_PROFILES.get(city.strip().lower())
        if profile is None:
            return None
        out = dict(profile)
        out["country_code"] = "us"
        out["forecast_source"] = self.name
        return out

    def normalize_city(self, city: str, country_code: Optional[str] = None) -> Optional[str]:
        """Return the canonical city key for *city* or ``None`` if unknown."""
        profile = self.city_profile(city, country_code=country_code)
        if profile is None:
            return None
        return str(profile["canonical"])

    def get_grid_info(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Look up the NOAA forecast grid for a given latitude/longitude.

        Returns a dict with keys ``office``, ``gridX``, ``gridY`` or *None* on
        failure.  Results are cached for 24 hours.
        """
        cache_key = f"grid:{lat:.4f},{lon:.4f}"
        cached = self.get_cached(cache_key, ttl=_GRID_TTL)
        if cached is not None:
            return cached

        url = f"https://api.weather.gov/points/{lat},{lon}"
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch grid info for %s,%s", lat, lon)
            return None

        try:
            props = data["properties"]  # type: ignore[index]
            result: Dict[str, Any] = {
                "office": props["gridId"],
                "gridX": props["gridX"],
                "gridY": props["gridY"],
            }
        except (KeyError, TypeError):
            self.logger.warning("Unexpected grid response for %s,%s", lat, lon)
            return None

        self.set_cached(cache_key, result)
        return result

    def get_point_metadata(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Return expanded ``/points`` metadata including raw grid-data URLs."""
        cache_key = f"pointmeta:{lat:.4f},{lon:.4f}"
        cached = self.get_cached(cache_key, ttl=_GRID_TTL)
        if cached is not None:
            return cached

        url = f"https://api.weather.gov/points/{lat},{lon}"
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch point metadata for %s,%s", lat, lon)
            return None

        try:
            props = data["properties"]  # type: ignore[index]
            result: Dict[str, Any] = {
                "office": props["gridId"],
                "gridX": props["gridX"],
                "gridY": props["gridY"],
                "forecast": props.get("forecast"),
                "forecastHourly": props.get("forecastHourly"),
                "forecastGridData": props.get("forecastGridData"),
                "observationStations": props.get("observationStations"),
            }
        except (KeyError, TypeError):
            self.logger.warning("Unexpected point metadata response for %s,%s", lat, lon)
            return None

        self.set_cached(cache_key, result)
        return result

    def get_forecast(self, city: str, country_code: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Return the hourly forecast periods for *city*.

        Returns a list of period dicts or *None* on failure.  Results are cached
        for 1 hour.
        """
        city_lower = city.strip().lower()
        profile = self.city_profile(city_lower)
        if profile is None:
            self.logger.warning("Unknown city: %s", city)
            return None
        coords = tuple(profile["coords"])
        canonical = str(profile["canonical"])

        cache_key = f"forecast:{canonical}"
        cached = self.get_cached(cache_key, ttl=_FORECAST_TTL)
        if cached is not None:
            return cached

        grid = self.get_grid_info(coords[0], coords[1])
        if grid is None:
            return None

        url = (
            f"https://api.weather.gov/gridpoints/"
            f"{grid['office']}/{grid['gridX']},{grid['gridY']}/forecast/hourly"
        )
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch forecast for %s", canonical)
            return None

        try:
            periods: List[Dict[str, Any]] = data["properties"]["periods"]  # type: ignore[index]
        except (KeyError, TypeError):
            self.logger.warning("Unexpected forecast response for %s", canonical)
            return None

        self.set_cached(cache_key, periods)
        return periods

    def get_grid_data(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the raw grid forecast properties for *city*."""
        city_lower = city.strip().lower()
        profile = self.city_profile(city_lower)
        if profile is None:
            self.logger.warning("Unknown city: %s", city)
            return None

        coords = tuple(profile["coords"])
        canonical = str(profile["canonical"])
        cache_key = f"griddata:{canonical}"
        cached = self.get_cached(cache_key, ttl=_GRID_DATA_TTL)
        if cached is not None:
            return cached

        point_meta = self.get_point_metadata(coords[0], coords[1])
        if point_meta is None:
            return None
        url = point_meta.get("forecastGridData")
        if not isinstance(url, str) or not url:
            return None
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch raw grid data for %s", canonical)
            return None
        try:
            props: Dict[str, Any] = data["properties"]  # type: ignore[index]
        except (KeyError, TypeError):
            self.logger.warning("Unexpected raw grid response for %s", canonical)
            return None
        self.set_cached(cache_key, props)
        return props

    def get_latest_observation(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the latest station observation for *city*.

        The returned dict contains the latest observed temperature in both
        Fahrenheit and Celsius when available, plus station identifiers that can
        be attached to strategy metadata.
        """
        profile = self.city_profile(city)
        if profile is None:
            self.logger.warning("Unknown city: %s", city)
            return None
        station_id = str(profile.get("station_id", "")).strip()
        if not station_id:
            return None

        canonical = str(profile["canonical"])
        cache_key = f"observation:{canonical}"
        cached = self.get_cached(cache_key, ttl=_OBS_TTL)
        if cached is not None:
            return cached

        url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.warning("Failed to fetch latest observation for %s", canonical)
            return None

        try:
            props = data["properties"]  # type: ignore[index]
            temp_c = props["temperature"]["value"]
        except (KeyError, TypeError):
            self.logger.warning("Unexpected observation response for %s", canonical)
            return None

        temperature_c = None if temp_c is None else float(temp_c)
        temperature_f = None
        if temperature_c is not None:
            temperature_f = (temperature_c * 9.0 / 5.0) + 32.0

        result = {
            "city": canonical,
            "station_id": station_id,
            "station_label": str(profile.get("station_label", station_id)),
            "timestamp": props.get("timestamp"),
            "temperature_c": temperature_c,
            "temperature_f": temperature_f,
        }
        self.set_cached(cache_key, result)
        return result

    def extract_city_from_question(self, question: str) -> Optional[str]:
        """Scan *question* for a known city name.

        Returns the normalised (lower-case) city name or *None* if no match is
        found.  Matching is case-insensitive and prefers the longest city name
        first so that ``"los angeles"`` is matched before ``"la"``.
        """
        q_lower = question.lower()
        for city in self._SORTED_CITY_NAMES:
            if re.search(rf"\b{re.escape(city)}\b", q_lower):
                return city
        return None

    def temperature_probability(
        self,
        city: str,
        threshold_f: float,
        above: bool = True,
        hours: int = 24,
    ) -> Optional[float]:
        """Estimate the probability of temperature being above/below a threshold.

        Looks at the next *hours* hourly forecast periods for *city* and returns
        the fraction of periods where the temperature is above (or below if
        ``above=False``) *threshold_f*.  Returns a float in ``[0.0, 1.0]`` or
        *None* on failure.
        """
        periods = self.get_forecast(city)
        if not periods:
            return None

        sliced = periods[:hours]
        if not sliced:
            return None

        count = 0
        for p in sliced:
            temp = p.get("temperature")
            if temp is None:
                continue
            if above and temp > threshold_f:
                count += 1
            elif not above and temp < threshold_f:
                count += 1

        return count / len(sliced)

    def precipitation_probability(
        self,
        city: str,
        hours: int = 24,
    ) -> Optional[float]:
        """Average probability-of-precipitation over the next *hours* periods.

        Returns a float in ``[0.0, 1.0]`` (converted from the percentage value
        returned by the API) or *None* on failure.  Periods with a null
        precipitation value are treated as 0%.
        """
        periods = self.get_forecast(city)
        if not periods:
            return None

        sliced = periods[:hours]
        if not sliced:
            return None

        total = 0.0
        for p in sliced:
            pop = p.get("probabilityOfPrecipitation")
            if isinstance(pop, dict):
                val = pop.get("value")
                if val is not None:
                    total += float(val)
            # If pop is None / missing / not a dict, contribute 0.

        return total / (len(sliced) * 100.0)
