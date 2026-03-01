"""Data layer -- providers, HTTP helpers, and caching."""
from __future__ import annotations

from typing import Dict, List, Optional

from data.base_provider import BaseDataProvider


class DataRegistry:
    """Central registry mapping provider names to instances."""

    def __init__(self) -> None:
        self._providers: Dict[str, BaseDataProvider] = {}

    def register(self, provider: BaseDataProvider) -> None:
        """Register a data provider under its name."""
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[BaseDataProvider]:
        """Get a provider by name. Returns None if not found."""
        return self._providers.get(name)

    def list_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def __len__(self) -> int:
        return len(self._providers)


__all__ = ["BaseDataProvider", "DataRegistry"]
