"""Abstract base class for all data providers."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseDataProvider(ABC):
    """Base class every data provider must inherit from.

    Provides:
    * A logger namespaced to ``data.<name>``.
    * A simple in-memory cache with per-key TTL expiry.
    """

    name: str = "base"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"data.{self.name}")
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}

    @abstractmethod
    def fetch(self, **kwargs: Any) -> Any:
        """Retrieve data from the upstream source."""
        ...

    def get_cached(self, key: str, ttl: float = 300.0) -> Optional[Any]:
        """Return the cached value for *key* if it was stored less than *ttl* seconds ago."""
        if key not in self._cache:
            return None
        age = time.time() - self._cache_ts.get(key, 0.0)
        if age > ttl:
            # Expired -- clean up.
            del self._cache[key]
            del self._cache_ts[key]
            return None
        return self._cache[key]

    def set_cached(self, key: str, value: Any) -> None:
        """Store *value* under *key* with the current timestamp."""
        self._cache[key] = value
        self._cache_ts[key] = time.time()
