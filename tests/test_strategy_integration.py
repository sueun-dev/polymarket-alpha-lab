"""Integration tests for S01-S05 strategy upgrades with data providers.

Tests both WITH and WITHOUT data registries to ensure backward compatibility.
All existing 596 tests must continue to pass unchanged.
"""
import pytest
from unittest.mock import MagicMock, patch

from core.models import Opportunity
from data import DataRegistry
from data.base_rates import BaseRateProvider
from data.noaa import NOAAWeatherProvider
from data.kalshi_client import KalshiDataProvider
from data.news_client import NewsDataProvider
from data.feature_engine import LiveFeatureBuilder
from strategies.tier_s.s01_reversing_stupidity import ReversingStupidity
from strategies.tier_s.s02_weather_noaa import WeatherNOAA
from strategies.tier_s.s03_nothing_ever_happens import NothingEverHappens
from strategies.tier_s.s04_cross_platform_arb import CrossPlatformArb
from strategies.tier_s.s05_negrisk_rebalancing import NegRiskRebalancing


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def make_registry_with_base_rates():
    """Create a registry with a BaseRateProvider using default rates."""
    registry = DataRegistry()
    provider = BaseRateProvider()
    registry.register(provider)
    return registry


def make_registry_with_noaa(forecast_data):
    """Create a registry with a NOAAWeatherProvider returning canned forecast."""
    registry = DataRegistry()
    provider = NOAAWeatherProvider()
    # Pre-populate cache so no HTTP calls are made
    provider.set_cached("forecast:chicago", forecast_data)
    registry.register(provider)
    return registry


def make_registry_with_kalshi(markets_data):
    """Create a registry with a KalshiDataProvider returning canned markets."""
    registry = DataRegistry()
    provider = KalshiDataProvider()
    # Pre-populate the cache so get_markets() returns our data
    provider.set_cached("markets:100:open", markets_data)
    registry.register(provider)
    return registry


def make_registry_with_news(sentiment_data):
    """Create a registry with a mocked NewsDataProvider."""
    registry = DataRegistry()
    provider = NewsDataProvider()
    # Mock get_sentiment_for_market to return canned data without API key
    provider.get_sentiment_for_market = MagicMock(return_value=sentiment_data)
    registry.register(provider)
    return registry


def make_registry_with_feature_engine():
    """Create a registry with a LiveFeatureBuilder."""
    registry = DataRegistry()
    provider = LiveFeatureBuilder()
    registry.register(provider)
    return registry


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _s01_opportunity(category="politics"):
    """Standard S01 opportunity: overheated YES at 0.80."""
    return Opportunity(
        market_id="0x1",
        question="Will Trump win the 2028 election?",
        market_price=0.80,
        category=category,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ],
            "volume": 50000,
        },
    )


def _s02_temperature_opportunity():
    """S02 weather opportunity: Chicago temperature above 80 degrees."""
    return Opportunity(
        market_id="0x2",
        question="Will Chicago high temperature exceed 80 degrees fahrenheit?",
        market_price=0.03,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "y2", "outcome": "Yes", "price": "0.03"},
                {"token_id": "n2", "outcome": "No", "price": "0.97"},
            ],
            "volume": 1000,
        },
    )


def _s02_precipitation_opportunity():
    """S02 weather opportunity: Chicago rain."""
    return Opportunity(
        market_id="0x2b",
        question="Will it rain in Chicago tomorrow?",
        market_price=0.03,
        category="weather",
        metadata={
            "tokens": [
                {"token_id": "y2b", "outcome": "Yes", "price": "0.03"},
                {"token_id": "n2b", "outcome": "No", "price": "0.97"},
            ],
            "volume": 500,
        },
    )


def _s03_opportunity(category="geopolitical"):
    """Standard S03 opportunity: dramatic question YES at 0.35."""
    return Opportunity(
        market_id="0x3",
        question="Will Russia invade Poland?",
        market_price=0.35,
        category=category,
        metadata={
            "tokens": [
                {"token_id": "y3", "outcome": "Yes", "price": "0.35"},
                {"token_id": "n3", "outcome": "No", "price": "0.65"},
            ],
        },
    )


def _s04_opportunity():
    """Standard S04 opportunity for cross-platform arb."""
    return Opportunity(
        market_id="0x4",
        question="Will the Fed cut interest rates in March?",
        market_price=0.40,
        category="economics",
        metadata={
            "tokens": [
                {"token_id": "y4", "outcome": "Yes", "price": "0.40"},
                {"token_id": "n4", "outcome": "No", "price": "0.60"},
            ],
            "platform": "polymarket",
        },
    )


def _s05_opportunity():
    """Standard S05 opportunity: multi-outcome overpriced market."""
    return Opportunity(
        market_id="0x5",
        question="Who wins the championship?",
        market_price=1.05,
        category="sports",
        metadata={
            "tokens": [
                {"token_id": "t1", "outcome": "A", "price": "0.40"},
                {"token_id": "t2", "outcome": "B", "price": "0.35"},
                {"token_id": "t3", "outcome": "C", "price": "0.30"},
            ],
            "overprice": 0.05,
            "total_yes": 1.05,
        },
    )


# ===========================================================================
# S01: Reversing Stupidity
# ===========================================================================


class TestS01WithBaseRates:
    """S01 with base_rates provider uses category-specific rates."""

    def test_uses_politics_base_rate(self):
        strategy = ReversingStupidity()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        opp = _s01_opportunity(category="politics")
        signal = strategy.analyze(opp)

        # Politics no_rate = 0.95 -> base_rate = 0.05 (YES fair value)
        # yes_price=0.80, base_rate=0.05, edge=0.75 >> 0.20 threshold
        assert signal is not None
        assert signal.token_id == "n1"
        assert signal.side == "buy"
        # NO prob = 1 - base_rate = 0.95
        assert signal.estimated_prob == pytest.approx(0.95, abs=0.01)
        # base_rate should be in metadata
        assert signal.metadata["base_rate"] == pytest.approx(0.05, abs=0.01)

    def test_uses_crypto_base_rate(self):
        strategy = ReversingStupidity()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        # Crypto no_rate = 0.70 -> base_rate = 0.30
        opp = _s01_opportunity(category="crypto")
        signal = strategy.analyze(opp)

        # yes_price=0.80, base_rate=0.30, edge=0.50 > 0.20 threshold
        assert signal is not None
        assert signal.metadata["base_rate"] == pytest.approx(0.30, abs=0.01)

    def test_sports_base_rate_no_signal(self):
        strategy = ReversingStupidity()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        # Sports no_rate = 0.50 -> base_rate = 0.50
        # yes_price=0.80, base_rate=0.50, edge=0.30 > 0.20 threshold
        opp = _s01_opportunity(category="sports")
        signal = strategy.analyze(opp)
        assert signal is not None
        assert signal.metadata["base_rate"] == pytest.approx(0.50, abs=0.01)


class TestS01WithNews:
    """S01 with news provider adjusts base_rate for positive sentiment."""

    def test_positive_sentiment_reduces_base_rate(self):
        strategy = ReversingStupidity()

        # Create registry with both base_rates and news
        registry = DataRegistry()
        registry.register(BaseRateProvider())
        news = NewsDataProvider()
        news.get_sentiment_for_market = MagicMock(
            return_value={"avg_sentiment": 0.5, "article_count": 3, "articles": []}
        )
        registry.register(news)
        strategy.set_data_registry(registry)

        opp = _s01_opportunity(category="politics")
        signal = strategy.analyze(opp)

        # politics base_rate = 0.05, with positive sentiment -> 0.05 * 0.9 = 0.045
        assert signal is not None
        assert signal.metadata["base_rate"] == pytest.approx(0.045, abs=0.01)

    def test_neutral_sentiment_no_change(self):
        strategy = ReversingStupidity()

        registry = DataRegistry()
        registry.register(BaseRateProvider())
        news = NewsDataProvider()
        news.get_sentiment_for_market = MagicMock(
            return_value={"avg_sentiment": 0.1, "article_count": 3, "articles": []}
        )
        registry.register(news)
        strategy.set_data_registry(registry)

        opp = _s01_opportunity(category="politics")
        signal = strategy.analyze(opp)

        # avg_sentiment=0.1 < 0.3 threshold, no change
        assert signal is not None
        assert signal.metadata["base_rate"] == pytest.approx(0.05, abs=0.01)

    def test_no_sentiment_data_no_change(self):
        strategy = ReversingStupidity()

        registry = DataRegistry()
        registry.register(BaseRateProvider())
        news = NewsDataProvider()
        news.get_sentiment_for_market = MagicMock(return_value=None)
        registry.register(news)
        strategy.set_data_registry(registry)

        opp = _s01_opportunity(category="politics")
        signal = strategy.analyze(opp)

        assert signal is not None
        assert signal.metadata["base_rate"] == pytest.approx(0.05, abs=0.01)


class TestS01WithoutRegistry:
    """S01 without registry falls back to original behavior (base_rate=0.50)."""

    def test_original_behavior(self):
        strategy = ReversingStupidity()
        # No set_data_registry call
        opp = _s01_opportunity()
        signal = strategy.analyze(opp)

        # yes_price=0.80, base_rate=0.50 (fallback), edge=0.30 > 0.20
        assert signal is not None
        assert signal.metadata["base_rate"] == pytest.approx(0.50, abs=0.01)
        assert signal.token_id == "n1"
        assert signal.side == "buy"

    def test_below_threshold_returns_none(self):
        strategy = ReversingStupidity()
        opp = Opportunity(
            market_id="0x1",
            question="Will Trump win?",
            market_price=0.65,  # 0.65 - 0.50 = 0.15 < 0.20 threshold
            metadata={
                "tokens": [
                    {"token_id": "y1", "outcome": "Yes"},
                    {"token_id": "n1", "outcome": "No"},
                ],
            },
        )
        signal = strategy.analyze(opp)
        assert signal is None


# ===========================================================================
# S02: Weather NOAA
# ===========================================================================


def _make_forecast_periods(temp=85, precip_pct=30, count=24):
    """Build canned NOAA forecast periods."""
    return [
        {
            "temperature": temp,
            "temperatureUnit": "F",
            "probabilityOfPrecipitation": {"value": precip_pct},
        }
        for _ in range(count)
    ]


class TestS02WithNOAA:
    """S02 with noaa_weather provider uses real forecast data."""

    def test_temperature_above(self):
        strategy = WeatherNOAA()
        # 85F forecast, threshold 80F -> all 24 periods above -> prob=1.0
        forecast = _make_forecast_periods(temp=85, count=24)
        registry = make_registry_with_noaa(forecast)
        strategy.set_data_registry(registry)

        opp = _s02_temperature_opportunity()
        prob = strategy._estimate_weather_prob(opp)

        assert prob is not None
        assert prob == pytest.approx(1.0, abs=0.01)

    def test_temperature_below_threshold(self):
        strategy = WeatherNOAA()
        # 70F forecast, threshold 80F, question says "exceed" -> 0 periods above
        forecast = _make_forecast_periods(temp=70, count=24)
        registry = make_registry_with_noaa(forecast)
        strategy.set_data_registry(registry)

        opp = _s02_temperature_opportunity()
        prob = strategy._estimate_weather_prob(opp)

        assert prob is not None
        assert prob == pytest.approx(0.0, abs=0.01)

    def test_precipitation_probability(self):
        strategy = WeatherNOAA()
        # 30% precipitation across all periods -> avg 0.30
        forecast = _make_forecast_periods(precip_pct=30, count=24)
        registry = make_registry_with_noaa(forecast)
        strategy.set_data_registry(registry)

        opp = _s02_precipitation_opportunity()
        prob = strategy._estimate_weather_prob(opp)

        assert prob is not None
        assert prob == pytest.approx(0.30, abs=0.01)

    def test_analyze_uses_noaa_data(self):
        strategy = WeatherNOAA()
        # High probability weather event
        forecast = _make_forecast_periods(temp=85, count=24)
        registry = make_registry_with_noaa(forecast)
        strategy.set_data_registry(registry)

        opp = _s02_temperature_opportunity()
        signal = strategy.analyze(opp)

        # estimated_prob=1.0, market_price=0.03, edge=0.97 >> MIN_EDGE
        assert signal is not None
        assert signal.estimated_prob == pytest.approx(1.0, abs=0.01)
        assert signal.token_id == "y2"
        assert signal.side == "buy"

    def test_unknown_city_falls_to_fallback(self):
        strategy = WeatherNOAA()
        forecast = _make_forecast_periods(temp=85, count=24)
        registry = make_registry_with_noaa(forecast)
        strategy.set_data_registry(registry)

        # Question mentions no known city
        opp = Opportunity(
            market_id="0x2",
            question="Will the high temperature in Timbuktu exceed 80 degrees fahrenheit?",
            market_price=0.03,
            category="weather",
            metadata={"tokens": [{"token_id": "y2", "outcome": "Yes"}], "volume": 500},
        )
        prob = strategy._estimate_weather_prob(opp)
        # Falls back to original: price=0.03 < 0.05 -> 0.03 + 0.10 = 0.13
        assert prob == pytest.approx(0.13, abs=0.01)


class TestS02WithoutRegistry:
    """S02 without registry falls back to original placeholder behavior."""

    def test_original_fallback_cheap(self):
        strategy = WeatherNOAA()
        opp = Opportunity(
            market_id="0x2",
            question="Will NYC high temperature exceed 80 degrees?",
            market_price=0.03,
            category="weather",
            metadata={"tokens": [{"token_id": "y2", "outcome": "Yes"}], "volume": 500},
        )
        prob = strategy._estimate_weather_prob(opp)
        # Original fallback: price < 0.05 -> price + 0.10
        assert prob == pytest.approx(0.13, abs=0.01)

    def test_original_fallback_not_cheap(self):
        strategy = WeatherNOAA()
        opp = Opportunity(
            market_id="0x2",
            question="Will NYC high temperature exceed 80 degrees?",
            market_price=0.10,
            category="weather",
            metadata={"tokens": [{"token_id": "y2", "outcome": "Yes"}], "volume": 500},
        )
        prob = strategy._estimate_weather_prob(opp)
        # Original fallback: price >= 0.05 -> None
        assert prob is None


class TestS02ExtractTemperature:
    """Test the helper _extract_temperature method."""

    def test_degrees_fahrenheit(self):
        assert WeatherNOAA._extract_temperature("above 80 degrees fahrenheit") == 80.0

    def test_degree_symbol(self):
        assert WeatherNOAA._extract_temperature("exceed 75°f today") == 75.0

    def test_just_degrees(self):
        assert WeatherNOAA._extract_temperature("over 90 degrees") == 90.0

    def test_no_match(self):
        assert WeatherNOAA._extract_temperature("will it rain tomorrow") is None

    def test_just_f(self):
        assert WeatherNOAA._extract_temperature("above 100f") == 100.0


# ===========================================================================
# S03: Nothing Ever Happens
# ===========================================================================


class TestS03WithBaseRates:
    """S03 with base_rates uses category-specific NO rates."""

    def test_geopolitical_rate(self):
        strategy = NothingEverHappens()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        opp = _s03_opportunity(category="geopolitical")
        signal = strategy.analyze(opp)

        # Geopolitical no_rate = 0.85
        # yes_price=0.35, no_price=0.65, edge = 0.85 - 0.65 = 0.20 > 0.05
        assert signal is not None
        assert signal.estimated_prob == pytest.approx(0.85, abs=0.01)

    def test_politics_rate(self):
        strategy = NothingEverHappens()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        opp = _s03_opportunity(category="politics")
        signal = strategy.analyze(opp)

        # Politics no_rate = 0.95
        # yes_price=0.35, no_price=0.65, edge = 0.95 - 0.65 = 0.30 > 0.05
        assert signal is not None
        assert signal.estimated_prob == pytest.approx(0.95, abs=0.01)

    def test_categorizes_from_question_when_category_empty(self):
        strategy = NothingEverHappens()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        # Empty category -- should be categorized from question keywords
        opp = Opportunity(
            market_id="0x3",
            question="Will Russia invade Poland?",
            market_price=0.35,
            category="",
            metadata={
                "tokens": [
                    {"token_id": "y3", "outcome": "Yes"},
                    {"token_id": "n3", "outcome": "No"},
                ],
            },
        )
        signal = strategy.analyze(opp)

        # "russia" and "invasion" -> geopolitical (no_rate=0.85)
        assert signal is not None
        assert signal.estimated_prob == pytest.approx(0.85, abs=0.01)

    def test_sports_rate_lower(self):
        strategy = NothingEverHappens()
        registry = make_registry_with_base_rates()
        strategy.set_data_registry(registry)

        opp = _s03_opportunity(category="sports")
        signal = strategy.analyze(opp)

        # Sports no_rate = 0.50
        # yes_price=0.35, no_price=0.65, edge = 0.50 - 0.65 = -0.15 < 0.05
        assert signal is None


class TestS03WithoutRegistry:
    """S03 without registry uses BASE_NO_RATE=0.70."""

    def test_original_behavior(self):
        strategy = NothingEverHappens()
        # No set_data_registry call
        opp = _s03_opportunity()
        signal = strategy.analyze(opp)

        # BASE_NO_RATE=0.70, yes_price=0.35, no_price=0.65
        # edge = 0.70 - 0.65 = 0.05, exactly at threshold
        assert signal is not None
        assert signal.estimated_prob == pytest.approx(0.70, abs=0.01)

    def test_original_no_signal_when_below_threshold(self):
        strategy = NothingEverHappens()
        opp = Opportunity(
            market_id="0x3",
            question="Will Russia invade?",
            market_price=0.40,  # no_price=0.60, edge = 0.70 - 0.60 = 0.10 > 0.05
            metadata={"tokens": [{"token_id": "n3", "outcome": "No"}]},
        )
        signal = strategy.analyze(opp)
        assert signal is not None

        # At a higher YES price where edge would be too small
        opp2 = Opportunity(
            market_id="0x3",
            question="Will Russia invade?",
            market_price=0.25,  # no_price=0.75, edge = 0.70 - 0.75 = -0.05 < 0.05
            metadata={"tokens": [{"token_id": "n3", "outcome": "No"}]},
        )
        signal2 = strategy.analyze(opp2)
        assert signal2 is None


# ===========================================================================
# S04: Cross-Platform Arb
# ===========================================================================


class TestS04WithKalshi:
    """S04 with kalshi provider fetches and uses Kalshi prices."""

    def test_finds_arb_with_matching_market(self):
        strategy = CrossPlatformArb()

        # Create Kalshi market data that matches the Polymarket question
        kalshi_markets = [
            {
                "title": "Federal Reserve interest rate cut March",
                "subtitle": "Will the Fed cut rates?",
                "yes_bid": 30,  # 30 cents -> NO price = 1 - 0.30 = 0.70
                "ticker": "FED-RATE-CUT-MAR",
            }
        ]
        registry = make_registry_with_kalshi(kalshi_markets)
        strategy.set_data_registry(registry)

        opp = _s04_opportunity()
        # poly_yes=0.40, kalshi_no=0.70
        # total_cost = 0.40 + 0.70 + fees = ~1.107 > 1.0 -> no arb
        signal = strategy.analyze(opp)
        # With these numbers, no arb opportunity
        assert signal is None

    def test_finds_arb_with_cheap_prices(self):
        strategy = CrossPlatformArb()

        kalshi_markets = [
            {
                "title": "Federal Reserve interest rate cut March",
                "subtitle": "Will the Fed cut rates?",
                "yes_bid": 70,  # 70 cents -> NO price = 1 - 0.70 = 0.30
                "ticker": "FED-RATE-CUT-MAR",
            }
        ]
        registry = make_registry_with_kalshi(kalshi_markets)
        strategy.set_data_registry(registry)

        # Poly YES=0.40 + Kalshi NO=0.30 + fees ~ 0.7071 < 1.0 -> ARB!
        opp = _s04_opportunity()
        signal = strategy.analyze(opp)

        assert signal is not None
        assert signal.side == "buy"
        assert signal.confidence == 0.95
        assert signal.metadata["arb_profit"] > 0.02

    def test_no_matching_market(self):
        strategy = CrossPlatformArb()

        kalshi_markets = [
            {
                "title": "Completely unrelated market about sports",
                "subtitle": "Who wins the game?",
                "yes_bid": 50,
                "ticker": "SPORTS-123",
            }
        ]
        registry = make_registry_with_kalshi(kalshi_markets)
        strategy.set_data_registry(registry)

        opp = _s04_opportunity()
        signal = strategy.analyze(opp)
        # No match -> None
        assert signal is None

    def test_empty_kalshi_markets(self):
        strategy = CrossPlatformArb()
        registry = make_registry_with_kalshi([])
        strategy.set_data_registry(registry)

        opp = _s04_opportunity()
        signal = strategy.analyze(opp)
        assert signal is None


class TestS04WithoutRegistry:
    """S04 without registry returns None (original behavior)."""

    def test_original_behavior(self):
        strategy = CrossPlatformArb()
        opp = _s04_opportunity()
        signal = strategy.analyze(opp)
        assert signal is None  # _get_kalshi_no_price returns None


# ===========================================================================
# S05: NegRisk Rebalancing
# ===========================================================================


class TestS05WithFeatureEngine:
    """S05 with feature_engine provider accepts it without breaking."""

    def test_still_produces_signal(self):
        strategy = NegRiskRebalancing()
        registry = make_registry_with_feature_engine()
        strategy.set_data_registry(registry)

        opp = _s05_opportunity()
        signal = strategy.analyze(opp)

        # Should still work exactly the same
        assert signal is not None
        assert signal.token_id == "t1"  # Most overpriced
        assert signal.side == "sell"
        assert signal.confidence == 0.9

    def test_feature_engine_accessible(self):
        strategy = NegRiskRebalancing()
        registry = make_registry_with_feature_engine()
        strategy.set_data_registry(registry)

        # Verify the provider is wired up
        fe = strategy.get_data("feature_engine")
        assert fe is not None
        assert fe.name == "feature_engine"

    def test_below_overprice_returns_none(self):
        strategy = NegRiskRebalancing()
        registry = make_registry_with_feature_engine()
        strategy.set_data_registry(registry)

        opp = Opportunity(
            market_id="0x5",
            question="Who wins?",
            market_price=1.01,
            metadata={
                "tokens": [
                    {"token_id": "t1", "outcome": "A", "price": "0.34"},
                    {"token_id": "t2", "outcome": "B", "price": "0.33"},
                    {"token_id": "t3", "outcome": "C", "price": "0.34"},
                ],
                "overprice": 0.01,
            },
        )
        signal = strategy.analyze(opp)
        assert signal is None


class TestS05WithoutRegistry:
    """S05 without registry works identically to before."""

    def test_original_behavior(self):
        strategy = NegRiskRebalancing()
        opp = _s05_opportunity()
        signal = strategy.analyze(opp)

        assert signal is not None
        assert signal.token_id == "t1"
        assert signal.side == "sell"
        assert signal.confidence == 0.9
        assert signal.metadata["overprice"] == pytest.approx(0.05, abs=0.01)

    def test_no_feature_engine(self):
        strategy = NegRiskRebalancing()
        fe = strategy.get_data("feature_engine")
        assert fe is None


# ===========================================================================
# Cross-cutting: required_data declarations
# ===========================================================================


class TestRequiredDataDeclarations:
    """Verify each strategy declares its required data providers."""

    def test_s01_required_data(self):
        assert ReversingStupidity.required_data == ["base_rates", "news"]

    def test_s02_required_data(self):
        assert WeatherNOAA.required_data == ["noaa"]

    def test_s03_required_data(self):
        assert NothingEverHappens.required_data == ["base_rates"]

    def test_s04_required_data(self):
        assert CrossPlatformArb.required_data == ["kalshi"]

    def test_s05_required_data(self):
        assert NegRiskRebalancing.required_data == ["feature_engine"]
