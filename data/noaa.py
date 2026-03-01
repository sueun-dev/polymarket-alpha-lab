"""NOAA Weather data provider using the free api.weather.gov API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

# Cache TTL constants (seconds)
_GRID_TTL = 86400.0  # 24 hours
_FORECAST_TTL = 3600.0  # 1 hour


class NOAAWeatherProvider(BaseDataProvider):
    """Fetches weather forecasts from the NOAA api.weather.gov service.

    Uses a two-step lookup:
    1. ``/points/{lat},{lon}`` to obtain the forecast grid office and coordinates.
    2. ``/gridpoints/{office}/{gridX},{gridY}/forecast/hourly`` for hourly data.

    No API key is required.
    """

    name = "noaa_weather"

    CITY_COORDS: Dict[str, tuple[float, float]] = {
        "new york": (40.7128, -74.0060),
        "nyc": (40.7128, -74.0060),
        "chicago": (41.8781, -87.6298),
        "miami": (25.7617, -80.1918),
        "los angeles": (34.0522, -118.2437),
        "la": (34.0522, -118.2437),
        "washington dc": (38.9072, -77.0369),
        "dc": (38.9072, -77.0369),
        "houston": (29.7604, -95.3698),
        "phoenix": (33.4484, -112.0740),
        "philadelphia": (39.9526, -75.1652),
        "san francisco": (37.7749, -122.4194),
        "sf": (37.7749, -122.4194),
        "seattle": (47.6062, -122.3321),
        "denver": (39.7392, -104.9903),
        "boston": (42.3601, -71.0589),
        "atlanta": (33.7490, -84.3880),
        "dallas": (32.7767, -96.7970),
        "las vegas": (36.1699, -115.1398),
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
        return self.get_forecast(city)

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

    def get_forecast(self, city: str) -> Optional[List[Dict[str, Any]]]:
        """Return the hourly forecast periods for *city*.

        Returns a list of period dicts or *None* on failure.  Results are cached
        for 1 hour.
        """
        city_lower = city.strip().lower()
        coords = self.CITY_COORDS.get(city_lower)
        if coords is None:
            self.logger.warning("Unknown city: %s", city)
            return None

        cache_key = f"forecast:{city_lower}"
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
            self.logger.warning("Failed to fetch forecast for %s", city_lower)
            return None

        try:
            periods: List[Dict[str, Any]] = data["properties"]["periods"]  # type: ignore[index]
        except (KeyError, TypeError):
            self.logger.warning("Unexpected forecast response for %s", city_lower)
            return None

        self.set_cached(cache_key, periods)
        return periods

    def extract_city_from_question(self, question: str) -> Optional[str]:
        """Scan *question* for a known city name.

        Returns the normalised (lower-case) city name or *None* if no match is
        found.  Matching is case-insensitive and prefers the longest city name
        first so that ``"los angeles"`` is matched before ``"la"``.
        """
        q_lower = question.lower()
        for city in self._SORTED_CITY_NAMES:
            if city in q_lower:
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
