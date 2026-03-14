"""Composite weather provider: NOAA when possible, Open-Meteo elsewhere."""
from __future__ import annotations

from typing import Any, Dict, Optional

from data.base_provider import BaseDataProvider
from data.noaa import NOAAWeatherProvider
from data.openmeteo import OpenMeteoProvider


class WeatherRouterProvider(BaseDataProvider):
    """Route weather requests to NOAA for mapped US cities and Open-Meteo otherwise."""

    name = "noaa_weather"

    def __init__(
        self,
        noaa_provider: Optional[NOAAWeatherProvider] = None,
        openmeteo_provider: Optional[OpenMeteoProvider] = None,
    ) -> None:
        super().__init__()
        self.noaa = noaa_provider or NOAAWeatherProvider()
        self.open_meteo = openmeteo_provider or OpenMeteoProvider()

    def fetch(self, **kwargs: Any) -> Any:
        city = str(kwargs.get("city") or "").strip()
        if not city:
            return None
        return self.get_forecast(city, country_code=kwargs.get("country_code"))

    def city_profile(self, city: str, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        profile = self.noaa.city_profile(city, country_code=country_code)
        if profile is not None:
            out = dict(profile)
            out["forecast_source"] = "noaa"
            return out
        profile = self.open_meteo.city_profile(city, country_code=country_code)
        if profile is not None:
            out = dict(profile)
            out["forecast_source"] = "open_meteo"
            return out
        return None

    def normalize_city(self, city: str, country_code: Optional[str] = None) -> Optional[str]:
        profile = self.city_profile(city, country_code=country_code)
        if profile is None:
            return None
        canonical = str(profile.get("canonical") or "").strip()
        return canonical or None

    def extract_city_from_question(self, question: str) -> Optional[str]:
        return self.noaa.extract_city_from_question(question)

    def _use_noaa(self, city: str) -> bool:
        return self.noaa.city_profile(city) is not None

    def get_forecast(self, city: str, country_code: Optional[str] = None):
        if self._use_noaa(city):
            return self.noaa.get_forecast(city, country_code=country_code)
        return self.open_meteo.get_forecast(city, country_code=country_code)

    def get_grid_data(self, city: str, country_code: Optional[str] = None):
        if self._use_noaa(city):
            return self.noaa.get_grid_data(city, country_code=country_code)
        return self.open_meteo.get_grid_data(city, country_code=country_code)

    def get_latest_observation(self, city: str, country_code: Optional[str] = None):
        if self._use_noaa(city):
            return self.noaa.get_latest_observation(city, country_code=country_code)
        return self.open_meteo.get_latest_observation(city, country_code=country_code)

    def get_daily_summary(self, city: str, country_code: Optional[str] = None):
        if self._use_noaa(city):
            return None
        return self.open_meteo.get_daily_summary(city, country_code=country_code)
