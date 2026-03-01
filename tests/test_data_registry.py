"""Tests for DataRegistry and BaseStrategy data wiring."""
from __future__ import annotations

from typing import Any, List, Optional

import pytest

from data import DataRegistry
from data.base_provider import BaseDataProvider
from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubProvider(BaseDataProvider):
    """Minimal concrete provider for testing."""

    def __init__(self, provider_name: str = "stub") -> None:
        self.name = provider_name
        super().__init__()

    def fetch(self, **kwargs: Any) -> Any:
        return {"provider": self.name}


class _StubStrategy(BaseStrategy):
    """Minimal concrete strategy for testing."""

    name = "stub_strategy"
    tier = "C"
    strategy_id = 999
    required_data = ["stub"]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        return []

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        return None


# ---------------------------------------------------------------------------
# DataRegistry tests
# ---------------------------------------------------------------------------


class TestDataRegistry:
    def test_register_and_get(self):
        reg = DataRegistry()
        p = _StubProvider("my_provider")
        reg.register(p)
        assert reg.get("my_provider") is p

    def test_get_missing_returns_none(self):
        reg = DataRegistry()
        assert reg.get("nonexistent") is None

    def test_list_providers_empty(self):
        reg = DataRegistry()
        assert reg.list_providers() == []

    def test_list_providers(self):
        reg = DataRegistry()
        reg.register(_StubProvider("alpha"))
        reg.register(_StubProvider("beta"))
        names = reg.list_providers()
        assert sorted(names) == ["alpha", "beta"]

    def test_len_empty(self):
        reg = DataRegistry()
        assert len(reg) == 0

    def test_len(self):
        reg = DataRegistry()
        reg.register(_StubProvider("a"))
        reg.register(_StubProvider("b"))
        reg.register(_StubProvider("c"))
        assert len(reg) == 3

    def test_register_multiple_providers(self):
        reg = DataRegistry()
        p1 = _StubProvider("provider_1")
        p2 = _StubProvider("provider_2")
        p3 = _StubProvider("provider_3")
        reg.register(p1)
        reg.register(p2)
        reg.register(p3)
        assert reg.get("provider_1") is p1
        assert reg.get("provider_2") is p2
        assert reg.get("provider_3") is p3
        assert len(reg) == 3

    def test_register_overwrites_same_name(self):
        reg = DataRegistry()
        p1 = _StubProvider("dup")
        p2 = _StubProvider("dup")
        reg.register(p1)
        reg.register(p2)
        assert reg.get("dup") is p2
        assert len(reg) == 1


# ---------------------------------------------------------------------------
# BaseStrategy.get_data tests
# ---------------------------------------------------------------------------


class TestBaseStrategyGetData:
    def test_get_data_without_registry_returns_none(self):
        """Backward compatibility: get_data returns None when no registry is set."""
        s = _StubStrategy()
        assert s.get_data("anything") is None

    def test_get_data_with_registry(self):
        s = _StubStrategy()
        reg = DataRegistry()
        p = _StubProvider("stub")
        reg.register(p)
        s.set_data_registry(reg)
        assert s.get_data("stub") is p

    def test_get_data_missing_provider_returns_none(self):
        s = _StubStrategy()
        reg = DataRegistry()
        s.set_data_registry(reg)
        assert s.get_data("nonexistent") is None


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestStrategyDataIntegration:
    def test_strategy_accesses_provider_via_registry(self):
        """Full flow: create registry, register providers, inject into strategy, access data."""
        reg = DataRegistry()
        weather = _StubProvider("noaa_weather")
        news = _StubProvider("news")
        reg.register(weather)
        reg.register(news)

        strategy = _StubStrategy()
        strategy.set_data_registry(reg)

        assert strategy.get_data("noaa_weather") is weather
        assert strategy.get_data("news") is news
        assert strategy.get_data("missing") is None

    def test_multiple_strategies_share_registry(self):
        """Multiple strategies can share the same data registry."""
        reg = DataRegistry()
        p = _StubProvider("shared")
        reg.register(p)

        s1 = _StubStrategy()
        s2 = _StubStrategy()
        s1.set_data_registry(reg)
        s2.set_data_registry(reg)

        assert s1.get_data("shared") is s2.get_data("shared")
        assert s1.get_data("shared") is p
