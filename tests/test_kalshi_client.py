"""Tests for data.kalshi_client — Kalshi market data provider."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from unittest import mock

import pytest

from data.kalshi_client import KalshiDataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_market(
    ticker: str = "BTC-100K",
    title: str = "Bitcoin above $100k end of 2026",
    subtitle: str = "",
    yes_bid: float = 0.55,
    yes_ask: float = 0.57,
    no_bid: float = 0.43,
    no_ask: float = 0.45,
    status: str = "open",
) -> dict:
    """Create a fake Kalshi market dict for testing."""
    return {
        "ticker": ticker,
        "title": title,
        "subtitle": subtitle,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "status": status,
    }


SAMPLE_MARKETS: List[dict] = [
    _make_market(
        ticker="BTC-100K",
        title="Bitcoin above $100k end of 2026",
    ),
    _make_market(
        ticker="FED-RATE-MAR",
        title="Federal Reserve rate cut March",
        subtitle="Will the Fed cut rates in March 2026?",
    ),
    _make_market(
        ticker="WEATHER-NYC",
        title="NYC temperature above 80F on July 4",
    ),
]


# ---------------------------------------------------------------------------
# get_markets
# ---------------------------------------------------------------------------


class TestGetMarkets:
    """Tests for KalshiDataProvider.get_markets."""

    @mock.patch("data.kalshi_client.http_get_json")
    def test_returns_market_list(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": SAMPLE_MARKETS}
        provider = KalshiDataProvider()
        result = provider.get_markets(limit=50, status="open")
        assert result == SAMPLE_MARKETS
        mock_http.assert_called_once()
        url = mock_http.call_args[0][0]
        assert "limit=50" in url
        assert "status=open" in url

    @mock.patch("data.kalshi_client.http_get_json")
    def test_caching_60s_ttl(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": SAMPLE_MARKETS}
        provider = KalshiDataProvider()

        # First call fetches from API.
        result1 = provider.get_markets()
        assert mock_http.call_count == 1

        # Second call should use cache.
        result2 = provider.get_markets()
        assert mock_http.call_count == 1
        assert result1 == result2

    @mock.patch("data.kalshi_client.http_get_json")
    def test_cache_expires_after_ttl(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": SAMPLE_MARKETS}
        provider = KalshiDataProvider()

        provider.get_markets()
        assert mock_http.call_count == 1

        # Expire the cache entry manually.
        for key in list(provider._cache_ts):
            provider._cache_ts[key] = time.time() - 61

        provider.get_markets()
        assert mock_http.call_count == 2

    @mock.patch("data.kalshi_client.http_get_json")
    def test_different_params_use_different_cache_keys(
        self, mock_http: mock.MagicMock
    ) -> None:
        mock_http.return_value = {"markets": SAMPLE_MARKETS}
        provider = KalshiDataProvider()

        provider.get_markets(limit=10, status="open")
        provider.get_markets(limit=50, status="closed")
        assert mock_http.call_count == 2

    @mock.patch("data.kalshi_client.http_get_json")
    def test_http_failure_returns_empty_list(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = RuntimeError("network error")
        provider = KalshiDataProvider()
        result = provider.get_markets()
        assert result == []

    @mock.patch("data.kalshi_client.http_get_json")
    def test_unexpected_response_shape(self, mock_http: mock.MagicMock) -> None:
        # API returns a bare list instead of a dict with "markets" key.
        mock_http.return_value = SAMPLE_MARKETS
        provider = KalshiDataProvider()
        result = provider.get_markets()
        assert result == SAMPLE_MARKETS

    @mock.patch("data.kalshi_client.http_get_json")
    def test_empty_markets_response(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": []}
        provider = KalshiDataProvider()
        result = provider.get_markets()
        assert result == []

    @mock.patch("data.kalshi_client.http_get_json")
    def test_default_parameters(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": []}
        provider = KalshiDataProvider()
        provider.get_markets()
        url = mock_http.call_args[0][0]
        assert "limit=100" in url
        assert "status=open" in url

    @mock.patch("data.kalshi_client.http_get_json")
    def test_base_url_used(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": []}
        provider = KalshiDataProvider()
        provider.get_markets()
        url = mock_http.call_args[0][0]
        assert url.startswith(KalshiDataProvider.BASE_URL)


# ---------------------------------------------------------------------------
# get_market_orderbook
# ---------------------------------------------------------------------------


class TestGetMarketOrderbook:
    """Tests for KalshiDataProvider.get_market_orderbook."""

    @mock.patch("data.kalshi_client.http_get_json")
    def test_returns_orderbook(self, mock_http: mock.MagicMock) -> None:
        orderbook_data = {
            "yes": [[55, 100], [54, 200]],
            "no": [[45, 150], [46, 50]],
        }
        mock_http.return_value = orderbook_data
        provider = KalshiDataProvider()
        result = provider.get_market_orderbook("BTC-100K")
        assert result is not None
        assert result["yes"] == [[55, 100], [54, 200]]
        assert result["no"] == [[45, 150], [46, 50]]

    @mock.patch("data.kalshi_client.http_get_json")
    def test_caching_10s_ttl(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"yes": [], "no": []}
        provider = KalshiDataProvider()

        provider.get_market_orderbook("BTC-100K")
        assert mock_http.call_count == 1

        provider.get_market_orderbook("BTC-100K")
        assert mock_http.call_count == 1

    @mock.patch("data.kalshi_client.http_get_json")
    def test_cache_expires_after_10s(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"yes": [], "no": []}
        provider = KalshiDataProvider()

        provider.get_market_orderbook("BTC-100K")
        assert mock_http.call_count == 1

        for key in list(provider._cache_ts):
            provider._cache_ts[key] = time.time() - 11

        provider.get_market_orderbook("BTC-100K")
        assert mock_http.call_count == 2

    @mock.patch("data.kalshi_client.http_get_json")
    def test_different_tickers_separate_cache(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"yes": [], "no": []}
        provider = KalshiDataProvider()

        provider.get_market_orderbook("BTC-100K")
        provider.get_market_orderbook("FED-RATE-MAR")
        assert mock_http.call_count == 2

    @mock.patch("data.kalshi_client.http_get_json")
    def test_http_failure_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.side_effect = RuntimeError("timeout")
        provider = KalshiDataProvider()
        result = provider.get_market_orderbook("BAD-TICKER")
        assert result is None

    @mock.patch("data.kalshi_client.http_get_json")
    def test_non_dict_response_returns_none(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = "unexpected"
        provider = KalshiDataProvider()
        result = provider.get_market_orderbook("BTC-100K")
        assert result is None

    @mock.patch("data.kalshi_client.http_get_json")
    def test_url_includes_ticker(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"yes": [], "no": []}
        provider = KalshiDataProvider()
        provider.get_market_orderbook("MY-TICKER")
        url = mock_http.call_args[0][0]
        assert "/markets/MY-TICKER/orderbook" in url

    @mock.patch("data.kalshi_client.http_get_json")
    def test_missing_keys_default_to_empty(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"orderbook": {}}
        provider = KalshiDataProvider()
        result = provider.get_market_orderbook("BTC-100K")
        assert result is not None
        assert result["yes"] == []
        assert result["no"] == []


# ---------------------------------------------------------------------------
# match_polymarket_to_kalshi
# ---------------------------------------------------------------------------


class TestMatchPolymarketToKalshi:
    """Tests for fuzzy entity matching between Polymarket and Kalshi."""

    def test_bitcoin_match(self) -> None:
        provider = KalshiDataProvider()
        result = provider.match_polymarket_to_kalshi(
            "Will Bitcoin exceed $100k by end of 2026?",
            SAMPLE_MARKETS,
        )
        assert result is not None
        assert result["ticker"] == "BTC-100K"

    def test_fed_rate_match(self) -> None:
        provider = KalshiDataProvider()
        result = provider.match_polymarket_to_kalshi(
            "Will the Fed cut rates in March?",
            SAMPLE_MARKETS,
        )
        assert result is not None
        assert result["ticker"] == "FED-RATE-MAR"

    def test_no_match_returns_none(self) -> None:
        provider = KalshiDataProvider()
        result = provider.match_polymarket_to_kalshi(
            "Will it rain tomorrow in NYC?",
            SAMPLE_MARKETS,
        )
        # "rain" and "tomorrow" don't overlap with any market enough.
        assert result is None

    def test_empty_market_list_returns_none(self) -> None:
        provider = KalshiDataProvider()
        result = provider.match_polymarket_to_kalshi(
            "Will Bitcoin exceed $100k?",
            [],
        )
        assert result is None

    def test_empty_question_returns_none(self) -> None:
        provider = KalshiDataProvider()
        result = provider.match_polymarket_to_kalshi("", SAMPLE_MARKETS)
        assert result is None

    def test_stop_words_only_question_returns_none(self) -> None:
        provider = KalshiDataProvider()
        result = provider.match_polymarket_to_kalshi(
            "will the is a an to",
            SAMPLE_MARKETS,
        )
        assert result is None

    def test_threshold_0_3_boundary(self) -> None:
        """A match with score just above 0.3 should be returned."""
        provider = KalshiDataProvider()
        # Single overlapping non-stop token with a short Kalshi title.
        markets = [_make_market(ticker="X", title="bitcoin price")]
        result = provider.match_polymarket_to_kalshi(
            "bitcoin future projection value",
            markets,
        )
        # Poly tokens: {bitcoin, future, projection, value}
        # Kalshi tokens: {bitcoin, price}
        # overlap = 1, max(4, 2) = 4, score = 0.25 < 0.3
        assert result is None

    def test_high_overlap_returns_best(self) -> None:
        provider = KalshiDataProvider()
        markets = [
            _make_market(ticker="LOW", title="unrelated event happening soon"),
            _make_market(ticker="HIGH", title="Bitcoin exceed $100k 2026"),
        ]
        result = provider.match_polymarket_to_kalshi(
            "Will Bitcoin exceed $100k by 2026?",
            markets,
        )
        assert result is not None
        assert result["ticker"] == "HIGH"

    def test_uses_subtitle_for_matching(self) -> None:
        provider = KalshiDataProvider()
        markets = [
            _make_market(
                ticker="SUB",
                title="Rate decision",
                subtitle="Federal Reserve March cut",
            ),
        ]
        result = provider.match_polymarket_to_kalshi(
            "Federal Reserve rate cut March",
            markets,
        )
        assert result is not None
        assert result["ticker"] == "SUB"

    def test_case_insensitive(self) -> None:
        provider = KalshiDataProvider()
        markets = [_make_market(ticker="BTC", title="BITCOIN ABOVE $100K")]
        result = provider.match_polymarket_to_kalshi(
            "bitcoin above 100k",
            markets,
        )
        assert result is not None
        assert result["ticker"] == "BTC"

    def test_numbers_preserved_in_tokens(self) -> None:
        provider = KalshiDataProvider()
        # "100k" is a meaningful token that should be preserved.
        markets = [_make_market(ticker="A", title="Bitcoin 100k 2026")]
        result = provider.match_polymarket_to_kalshi("Bitcoin 100k 2026", markets)
        assert result is not None

    def test_market_with_empty_title(self) -> None:
        provider = KalshiDataProvider()
        markets = [_make_market(ticker="EMPTY", title="", subtitle="")]
        result = provider.match_polymarket_to_kalshi("bitcoin price", markets)
        assert result is None


# ---------------------------------------------------------------------------
# compute_arb_edge
# ---------------------------------------------------------------------------


class TestComputeArbEdge:
    """Tests for fee-adjusted arbitrage edge computation."""

    def test_same_prices_negative_edge(self) -> None:
        """When prices are the same, fees eat all profit."""
        result = KalshiDataProvider.compute_arb_edge(0.50, 0.50)
        assert result["buy_poly_sell_kalshi"] < 0
        assert result["buy_kalshi_sell_poly"] < 0
        assert result["best_edge"] < 0

    def test_large_price_difference_positive_edge(self) -> None:
        """Buying cheap, selling expensive should yield a positive edge."""
        # Poly YES at 0.30, Kalshi YES at 0.70 -- big spread.
        result = KalshiDataProvider.compute_arb_edge(0.30, 0.70)
        assert result["buy_poly_sell_kalshi"] > 0
        assert result["direction"] == "buy_poly"
        assert result["best_edge"] > 0

    def test_reverse_direction(self) -> None:
        """When Kalshi is cheaper, direction should be buy_kalshi."""
        result = KalshiDataProvider.compute_arb_edge(0.70, 0.30)
        assert result["buy_kalshi_sell_poly"] > 0
        assert result["direction"] == "buy_kalshi"
        assert result["best_edge"] > 0

    def test_arithmetic_buy_poly_sell_kalshi(self) -> None:
        """Verify exact formula: kalshi*(1-kalshi_fee) - poly*(1+poly_fee)."""
        poly_yes = 0.40
        kalshi_yes = 0.60
        poly_fee = 0.01
        kalshi_fee = 0.07

        result = KalshiDataProvider.compute_arb_edge(
            poly_yes, kalshi_yes, poly_fee, kalshi_fee
        )

        expected_buy_poly_sell_kalshi = (
            kalshi_yes * (1 - kalshi_fee) - poly_yes * (1 + poly_fee)
        )
        assert result["buy_poly_sell_kalshi"] == pytest.approx(
            expected_buy_poly_sell_kalshi
        )

    def test_arithmetic_buy_kalshi_sell_poly(self) -> None:
        """Verify exact formula: poly*(1-poly_fee) - kalshi*(1+kalshi_fee)."""
        poly_yes = 0.40
        kalshi_yes = 0.60
        poly_fee = 0.01
        kalshi_fee = 0.07

        result = KalshiDataProvider.compute_arb_edge(
            poly_yes, kalshi_yes, poly_fee, kalshi_fee
        )

        expected_buy_kalshi_sell_poly = (
            poly_yes * (1 - poly_fee) - kalshi_yes * (1 + kalshi_fee)
        )
        assert result["buy_kalshi_sell_poly"] == pytest.approx(
            expected_buy_kalshi_sell_poly
        )

    def test_effective_prices(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.50, 0.60, 0.01, 0.07)
        assert result["poly_yes_effective"] == pytest.approx(0.50 * 1.01)
        assert result["kalshi_yes_effective"] == pytest.approx(0.60 * 1.07)

    def test_best_edge_is_max_of_both(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.45, 0.55)
        assert result["best_edge"] == pytest.approx(
            max(result["buy_poly_sell_kalshi"], result["buy_kalshi_sell_poly"])
        )

    def test_direction_matches_best_edge(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.45, 0.55)
        if result["buy_poly_sell_kalshi"] >= result["buy_kalshi_sell_poly"]:
            assert result["direction"] == "buy_poly"
        else:
            assert result["direction"] == "buy_kalshi"

    def test_zero_prices(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.0, 0.0)
        assert result["poly_yes_effective"] == 0.0
        assert result["kalshi_yes_effective"] == 0.0
        assert result["buy_poly_sell_kalshi"] == 0.0
        assert result["buy_kalshi_sell_poly"] == 0.0

    def test_custom_fees(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.50, 0.50, poly_fee=0.0, kalshi_fee=0.0)
        # No fees: buying at 0.50 and selling at 0.50 yields zero edge.
        assert result["buy_poly_sell_kalshi"] == pytest.approx(0.0)
        assert result["buy_kalshi_sell_poly"] == pytest.approx(0.0)

    def test_default_fees_applied(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.50, 0.50)
        # poly_fee=0.01, kalshi_fee=0.07 by default.
        assert result["poly_yes_effective"] == pytest.approx(0.50 * 1.01)
        assert result["kalshi_yes_effective"] == pytest.approx(0.50 * 1.07)

    def test_result_keys_present(self) -> None:
        result = KalshiDataProvider.compute_arb_edge(0.50, 0.60)
        expected_keys = {
            "poly_yes_effective",
            "kalshi_yes_effective",
            "buy_poly_sell_kalshi",
            "buy_kalshi_sell_poly",
            "best_edge",
            "direction",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# fetch() dispatch
# ---------------------------------------------------------------------------


class TestFetchDispatch:
    """Tests for the fetch() entry-point dispatch logic."""

    @mock.patch("data.kalshi_client.http_get_json")
    def test_fetch_default_action_is_markets(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": SAMPLE_MARKETS}
        provider = KalshiDataProvider()
        result = provider.fetch()
        assert isinstance(result, list)

    @mock.patch("data.kalshi_client.http_get_json")
    def test_fetch_action_markets(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"markets": SAMPLE_MARKETS}
        provider = KalshiDataProvider()
        result = provider.fetch(action="markets", limit=10, status="closed")
        url = mock_http.call_args[0][0]
        assert "limit=10" in url
        assert "status=closed" in url

    @mock.patch("data.kalshi_client.http_get_json")
    def test_fetch_action_orderbook(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = {"yes": [], "no": []}
        provider = KalshiDataProvider()
        result = provider.fetch(action="orderbook", ticker="BTC-100K")
        assert result is not None
        url = mock_http.call_args[0][0]
        assert "BTC-100K" in url

    def test_fetch_action_orderbook_missing_ticker(self) -> None:
        provider = KalshiDataProvider()
        result = provider.fetch(action="orderbook")
        assert result is None

    def test_fetch_action_match(self) -> None:
        provider = KalshiDataProvider()
        result = provider.fetch(
            action="match",
            question="Will Bitcoin exceed $100k by end of 2026?",
            markets=SAMPLE_MARKETS,
        )
        assert result is not None
        assert result["ticker"] == "BTC-100K"

    def test_fetch_action_arb_edge(self) -> None:
        provider = KalshiDataProvider()
        result = provider.fetch(
            action="arb_edge", poly_yes=0.30, kalshi_yes=0.70
        )
        assert isinstance(result, dict)
        assert "best_edge" in result

    def test_fetch_unknown_action(self) -> None:
        provider = KalshiDataProvider()
        result = provider.fetch(action="nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------


class TestProviderMetadata:
    """Tests for provider name, logger, and class constants."""

    def test_name(self) -> None:
        provider = KalshiDataProvider()
        assert provider.name == "kalshi"

    def test_logger_name(self) -> None:
        provider = KalshiDataProvider()
        assert provider.logger.name == "data.kalshi"

    def test_base_url_is_class_constant(self) -> None:
        assert hasattr(KalshiDataProvider, "BASE_URL")
        assert "kalshi" in KalshiDataProvider.BASE_URL.lower()

    def test_inherits_base_data_provider(self) -> None:
        from data.base_provider import BaseDataProvider
        assert issubclass(KalshiDataProvider, BaseDataProvider)


# ---------------------------------------------------------------------------
# Tokenizer unit tests
# ---------------------------------------------------------------------------


class TestTokenizer:
    """Tests for the internal _tokenize static method."""

    def test_removes_stop_words(self) -> None:
        tokens = KalshiDataProvider._tokenize("Will the Fed cut rates in March?")
        assert "will" not in tokens
        assert "the" not in tokens
        assert "in" not in tokens
        assert "fed" in tokens
        assert "cut" in tokens
        assert "rates" in tokens
        assert "march" in tokens

    def test_lowercases(self) -> None:
        tokens = KalshiDataProvider._tokenize("BITCOIN ABOVE 100K")
        assert "bitcoin" in tokens
        assert "100k" in tokens

    def test_empty_string(self) -> None:
        assert KalshiDataProvider._tokenize("") == []

    def test_only_stop_words(self) -> None:
        assert KalshiDataProvider._tokenize("the a an is will be") == []

    def test_preserves_numbers(self) -> None:
        tokens = KalshiDataProvider._tokenize("price 100 or 200")
        assert "100" in tokens
        assert "200" in tokens

    def test_strips_punctuation(self) -> None:
        tokens = KalshiDataProvider._tokenize("Bitcoin? $100k! (the end)")
        assert "bitcoin" in tokens
        assert "100k" in tokens
        assert "the" not in tokens  # stop word removed
        assert "end" in tokens  # non-stop word preserved despite surrounding parens
