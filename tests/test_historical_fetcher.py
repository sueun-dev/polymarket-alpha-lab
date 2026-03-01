"""Tests for data.historical_fetcher -- MarketSample, normalize_yes_no, and HistoricalFetcher."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, List, Tuple
from unittest import mock

import pytest

from data.historical_fetcher import HistoricalFetcher, MarketSample, normalize_yes_no


# ---------------------------------------------------------------------------
# normalize_yes_no
# ---------------------------------------------------------------------------


class TestNormalizeYesNo:
    """Cover common outcome-label variants for normalize_yes_no."""

    def test_yes_no_standard(self):
        assert normalize_yes_no(["Yes", "No"]) == {"yes": 0, "no": 1}

    def test_no_yes_reversed(self):
        assert normalize_yes_no(["No", "Yes"]) == {"no": 0, "yes": 1}

    def test_uppercase(self):
        assert normalize_yes_no(["YES", "NO"]) == {"yes": 0, "no": 1}

    def test_lowercase(self):
        assert normalize_yes_no(["yes", "no"]) == {"yes": 0, "no": 1}

    def test_y_n(self):
        assert normalize_yes_no(["y", "n"]) == {"yes": 0, "no": 1}

    def test_true_false(self):
        assert normalize_yes_no(["true", "false"]) == {"yes": 0, "no": 1}

    def test_one_zero(self):
        assert normalize_yes_no(["1", "0"]) == {"yes": 0, "no": 1}

    def test_whitespace_stripped(self):
        assert normalize_yes_no(["  Yes ", " No  "]) == {"yes": 0, "no": 1}

    def test_empty_list(self):
        assert normalize_yes_no([]) == {}

    def test_unrecognised_labels(self):
        result = normalize_yes_no(["Red", "Blue"])
        assert result == {}

    def test_single_yes_only(self):
        result = normalize_yes_no(["Yes"])
        assert result == {"yes": 0}

    def test_mixed_case_true_false(self):
        assert normalize_yes_no(["TRUE", "FALSE"]) == {"yes": 0, "no": 1}


# ---------------------------------------------------------------------------
# HistoricalFetcher.price_at_or_before (static)
# ---------------------------------------------------------------------------


class TestPriceAtOrBefore:
    """Binary search over (timestamp, price) history."""

    def test_empty_history(self):
        assert HistoricalFetcher.price_at_or_before([], 100) is None

    def test_exact_match_single(self):
        history = [(100, 0.5)]
        assert HistoricalFetcher.price_at_or_before(history, 100) == 0.5

    def test_target_before_first(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.price_at_or_before(history, 50) is None

    def test_target_after_last(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.price_at_or_before(history, 300) == 0.6

    def test_exact_match_middle(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7)]
        assert HistoricalFetcher.price_at_or_before(history, 200) == 0.6

    def test_between_entries(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7)]
        # 150 is between 100 and 200 -> should return 0.5 (at 100)
        assert HistoricalFetcher.price_at_or_before(history, 150) == 0.5

    def test_between_last_two(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7)]
        assert HistoricalFetcher.price_at_or_before(history, 250) == 0.6

    def test_exact_last_entry(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7)]
        assert HistoricalFetcher.price_at_or_before(history, 300) == 0.7

    def test_target_equals_first(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.price_at_or_before(history, 100) == 0.5

    def test_large_history_binary_search(self):
        # Ensure binary search works correctly on a larger dataset
        history = [(i * 10, i * 0.01) for i in range(1, 101)]  # 10..1000
        assert HistoricalFetcher.price_at_or_before(history, 500) == 0.50
        assert HistoricalFetcher.price_at_or_before(history, 505) == 0.50
        assert HistoricalFetcher.price_at_or_before(history, 5) is None
        assert HistoricalFetcher.price_at_or_before(history, 1001) == 1.0


# ---------------------------------------------------------------------------
# HistoricalFetcher.window_prices (static)
# ---------------------------------------------------------------------------


class TestWindowPrices:
    """Selecting prices in a [start_ts, end_ts] window."""

    def test_empty_history(self):
        assert HistoricalFetcher.window_prices([], 100, 200) == []

    def test_all_within_range(self):
        history = [(100, 0.5), (150, 0.6), (200, 0.7)]
        assert HistoricalFetcher.window_prices(history, 100, 200) == [0.5, 0.6, 0.7]

    def test_none_within_range(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.window_prices(history, 300, 400) == []

    def test_partial_range(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7), (400, 0.8)]
        assert HistoricalFetcher.window_prices(history, 150, 350) == [0.6, 0.7]

    def test_inclusive_boundaries(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7)]
        result = HistoricalFetcher.window_prices(history, 100, 300)
        assert result == [0.5, 0.6, 0.7]

    def test_single_point(self):
        history = [(100, 0.5), (200, 0.6), (300, 0.7)]
        result = HistoricalFetcher.window_prices(history, 200, 200)
        assert result == [0.6]

    def test_range_before_history(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.window_prices(history, 10, 50) == []

    def test_range_after_history(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.window_prices(history, 300, 400) == []

    def test_start_equals_end_no_match(self):
        history = [(100, 0.5), (200, 0.6)]
        assert HistoricalFetcher.window_prices(history, 150, 150) == []


# ---------------------------------------------------------------------------
# HistoricalFetcher.fetch_closed_binary_markets (mocked HTTP)
# ---------------------------------------------------------------------------


def _make_gamma_market(
    *,
    market_id: str = "m1",
    question: str = "Will it rain?",
    category: str = "weather",
    outcomes: list | None = None,
    token_ids: list | None = None,
    prices: list | None = None,
    closed_time: str = "2024-06-01T00:00:00Z",
) -> dict:
    """Helper to build a single Gamma API market dict."""
    return {
        "id": market_id,
        "question": question,
        "category": category,
        "outcomes": json.dumps(outcomes or ["Yes", "No"]),
        "clobTokenIds": json.dumps(token_ids or ["tok_yes", "tok_no"]),
        "outcomePrices": json.dumps(prices or ["1.0", "0.0"]),
        "closedTime": closed_time,
    }


class TestFetchClosedBinaryMarkets:
    """Verify pagination, filtering, and parsing with mocked HTTP."""

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_single_page_single_market(self, mock_http):
        market = _make_gamma_market()
        mock_http.return_value = [market]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].market_id == "m1"
        assert samples[0].question == "Will it rain?"
        assert samples[0].category == "weather"
        assert samples[0].yes_token == "tok_yes"
        assert samples[0].yes_won is True

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_yes_lost(self, mock_http):
        market = _make_gamma_market(prices=["0.0", "1.0"])
        mock_http.return_value = [market]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].yes_won is False

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_pagination(self, mock_http):
        """Two pages -- second page is shorter than page_size, signalling end."""
        page1 = [
            _make_gamma_market(market_id="m1", closed_time="2024-06-01T00:00:00Z"),
            _make_gamma_market(market_id="m2", closed_time="2024-07-01T00:00:00Z"),
        ]
        page2 = [
            _make_gamma_market(market_id="m3", closed_time="2024-05-01T00:00:00Z"),
        ]
        mock_http.side_effect = [page1, page2]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=2)

        assert len(samples) == 3
        assert mock_http.call_count == 2
        # Should be sorted chronologically (oldest first)
        assert samples[0].market_id == "m3"
        assert samples[1].market_id == "m1"
        assert samples[2].market_id == "m2"

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_max_markets_limit_respected(self, mock_http):
        page = [
            _make_gamma_market(market_id=f"m{i}", closed_time="2024-06-01T00:00:00Z")
            for i in range(5)
        ]
        mock_http.return_value = page

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=3, page_size=10)

        assert len(samples) == 3

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_non_binary_markets(self, mock_http):
        """Markets with != 2 outcomes are skipped."""
        bad_market = {
            "id": "m_bad",
            "question": "Multi-outcome?",
            "category": "test",
            "outcomes": json.dumps(["A", "B", "C"]),
            "clobTokenIds": json.dumps(["t1", "t2", "t3"]),
            "outcomePrices": json.dumps(["0.3", "0.3", "0.4"]),
            "closedTime": "2024-06-01T00:00:00Z",
        }
        good_market = _make_gamma_market(market_id="m_good")
        mock_http.return_value = [bad_market, good_market]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].market_id == "m_good"

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_unresolved_markets(self, mock_http):
        """Markets where max price < 0.9 are skipped."""
        unresolved = _make_gamma_market(market_id="m_unres", prices=["0.5", "0.5"])
        resolved = _make_gamma_market(market_id="m_res", prices=["0.95", "0.05"])
        mock_http.return_value = [unresolved, resolved]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].market_id == "m_res"

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_missing_close_ts(self, mock_http):
        """Markets with no parseable close timestamp are skipped."""
        market = _make_gamma_market(market_id="m_nodate")
        del market["closedTime"]
        mock_http.return_value = [market]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 0

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_empty_batch_stops_pagination(self, mock_http):
        mock_http.return_value = []
        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 0
        assert mock_http.call_count == 1

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_non_list_batch_stops_pagination(self, mock_http):
        mock_http.return_value = {"error": "bad request"}
        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 0

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_non_dict_entries(self, mock_http):
        mock_http.return_value = ["not_a_dict", _make_gamma_market(market_id="m_ok")]
        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].market_id == "m_ok"

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_empty_token(self, mock_http):
        market = _make_gamma_market(token_ids=["", "tok_no"])
        mock_http.return_value = [market]
        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 0

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_empty_market_id(self, mock_http):
        market = _make_gamma_market(market_id="")
        mock_http.return_value = [market]
        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 0

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_fallback_to_endDate(self, mock_http):
        """If closedTime is absent, fall back to endDate."""
        market = _make_gamma_market(market_id="m_fb")
        del market["closedTime"]
        market["endDate"] = "2024-06-01T00:00:00Z"
        mock_http.return_value = [market]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].market_id == "m_fb"

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_fallback_to_endDateIso(self, mock_http):
        """If closedTime and endDate are absent, fall back to endDateIso."""
        market = _make_gamma_market(market_id="m_iso")
        del market["closedTime"]
        market["endDateIso"] = "2024-06-01T00:00:00Z"
        mock_http.return_value = [market]

        fetcher = HistoricalFetcher()
        samples = fetcher.fetch_closed_binary_markets(max_markets=10, page_size=100)

        assert len(samples) == 1
        assert samples[0].market_id == "m_iso"


# ---------------------------------------------------------------------------
# HistoricalFetcher.load_or_fetch_history (mocked HTTP + temp cache)
# ---------------------------------------------------------------------------


class TestLoadOrFetchHistory:
    """Test fetching and caching of price histories."""

    def _clob_response(self, points: List[Tuple[int, float]]) -> dict:
        """Build a CLOB prices-history response dict."""
        return {"history": [{"t": t, "p": p} for t, p in points]}

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_fetches_and_caches(self, mock_http):
        points = [(100, 0.5), (200, 0.6), (300, 0.7)]
        mock_http.return_value = self._clob_response(points)

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))
            result = fetcher.load_or_fetch_history("tok_abc", fidelity=1)

            assert result == points
            assert mock_http.call_count == 1

            # Verify the cache file was written
            cache_file = Path(tmpdir) / "histories" / "tok_abc.json"
            assert cache_file.exists()
            cached_data = json.loads(cache_file.read_text())
            assert cached_data == [[100, 0.5], [200, 0.6], [300, 0.7]]

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_reads_from_cache(self, mock_http):
        """Second call should read from cache, not HTTP."""
        points = [(100, 0.5), (200, 0.6)]
        mock_http.return_value = self._clob_response(points)

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))

            # First call: fetches from HTTP
            result1 = fetcher.load_or_fetch_history("tok_cached")
            assert mock_http.call_count == 1
            assert result1 == points

            # Second call: reads from cache
            result2 = fetcher.load_or_fetch_history("tok_cached")
            assert mock_http.call_count == 1  # Not called again
            assert result2 == points

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_sorts_history_chronologically(self, mock_http):
        # Return out-of-order points
        response = {"history": [{"t": 300, "p": 0.7}, {"t": 100, "p": 0.5}, {"t": 200, "p": 0.6}]}
        mock_http.return_value = response

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))
            result = fetcher.load_or_fetch_history("tok_unordered")

            assert result == [(100, 0.5), (200, 0.6), (300, 0.7)]

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_empty_history_from_api(self, mock_http):
        mock_http.return_value = {"history": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))
            result = fetcher.load_or_fetch_history("tok_empty")

            assert result == []
            # Cache file should still be written (with empty list)
            cache_file = Path(tmpdir) / "histories" / "tok_empty.json"
            assert cache_file.exists()

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_skips_invalid_rows(self, mock_http):
        """Rows missing t or p, or with non-dict entries, are skipped."""
        response = {
            "history": [
                {"t": 100, "p": 0.5},
                {"t": None, "p": 0.6},  # bad t
                {"t": 200},  # missing p
                "not a dict",  # non-dict
                {"t": 300, "p": 0.7},
            ]
        }
        mock_http.return_value = response

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))
            result = fetcher.load_or_fetch_history("tok_partial")

            assert result == [(100, 0.5), (300, 0.7)]

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_non_dict_payload(self, mock_http):
        """If the API returns a non-dict, history should be empty."""
        mock_http.return_value = "unexpected"

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))
            result = fetcher.load_or_fetch_history("tok_bad_payload")

            assert result == []

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_corrupt_cache_refetches(self, mock_http):
        """If cache file is corrupt, re-fetch from API."""
        points = [(100, 0.5)]
        mock_http.return_value = self._clob_response(points)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            histories_dir = cache_dir / "histories"
            histories_dir.mkdir(parents=True, exist_ok=True)

            # Write corrupt cache
            (histories_dir / "tok_corrupt.json").write_text("not valid json{{{")

            fetcher = HistoricalFetcher(cache_dir=cache_dir)
            result = fetcher.load_or_fetch_history("tok_corrupt")

            assert result == points
            assert mock_http.call_count == 1

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_empty_cache_file_refetches(self, mock_http):
        """If cache file has an empty list, re-fetch from API."""
        points = [(100, 0.5)]
        mock_http.return_value = self._clob_response(points)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            histories_dir = cache_dir / "histories"
            histories_dir.mkdir(parents=True, exist_ok=True)

            # Write empty list cache (valid JSON but no data)
            (histories_dir / "tok_empty_cache.json").write_text("[]")

            fetcher = HistoricalFetcher(cache_dir=cache_dir)
            result = fetcher.load_or_fetch_history("tok_empty_cache")

            # Empty list in cache means re-fetch
            assert result == points
            assert mock_http.call_count == 1

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_fidelity_parameter_passed(self, mock_http):
        mock_http.return_value = {"history": [{"t": 100, "p": 0.5}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = HistoricalFetcher(cache_dir=Path(tmpdir))
            fetcher.load_or_fetch_history("tok_fid", fidelity=60)

            call_url = mock_http.call_args[0][0]
            assert "fidelity=60" in call_url

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_creates_cache_directories(self, mock_http):
        mock_http.return_value = {"history": [{"t": 100, "p": 0.5}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            deep_cache = Path(tmpdir) / "deep" / "nested" / "cache"
            fetcher = HistoricalFetcher(cache_dir=deep_cache)
            fetcher.load_or_fetch_history("tok_dirs")

            assert (deep_cache / "histories" / "tok_dirs.json").exists()


# ---------------------------------------------------------------------------
# HistoricalFetcher.fetch (entry point delegation)
# ---------------------------------------------------------------------------


class TestFetchEntryPoint:
    """The fetch() method delegates to fetch_closed_binary_markets."""

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_fetch_delegates(self, mock_http):
        market = _make_gamma_market(market_id="m_delegate")
        mock_http.return_value = [market]

        fetcher = HistoricalFetcher()
        result = fetcher.fetch(max_markets=5, page_size=10)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].market_id == "m_delegate"

    @mock.patch("data.historical_fetcher.http_get_json")
    def test_fetch_default_params(self, mock_http):
        mock_http.return_value = []
        fetcher = HistoricalFetcher()
        result = fetcher.fetch()
        assert result == []


# ---------------------------------------------------------------------------
# HistoricalFetcher construction
# ---------------------------------------------------------------------------


class TestHistoricalFetcherInit:
    """Test constructor defaults and configuration."""

    def test_default_cache_dir(self):
        fetcher = HistoricalFetcher()
        assert fetcher.cache_dir == Path("data/cache/")

    def test_custom_cache_dir(self):
        fetcher = HistoricalFetcher(cache_dir=Path("/tmp/test_cache"))
        assert fetcher.cache_dir == Path("/tmp/test_cache")

    def test_name(self):
        fetcher = HistoricalFetcher()
        assert fetcher.name == "historical_fetcher"

    def test_logger_name(self):
        fetcher = HistoricalFetcher()
        assert fetcher.logger.name == "data.historical_fetcher"

    def test_inherits_base_provider(self):
        from data.base_provider import BaseDataProvider

        fetcher = HistoricalFetcher()
        assert isinstance(fetcher, BaseDataProvider)

    def test_has_in_memory_cache(self):
        fetcher = HistoricalFetcher()
        fetcher.set_cached("test_key", "test_value")
        assert fetcher.get_cached("test_key") == "test_value"


# ---------------------------------------------------------------------------
# MarketSample dataclass
# ---------------------------------------------------------------------------


class TestMarketSample:
    """Basic sanity checks on the dataclass."""

    def test_creation(self):
        sample = MarketSample(
            market_id="m1",
            question="Will it rain?",
            category="weather",
            close_ts=1717200000,
            yes_token="tok_yes",
            yes_won=True,
        )
        assert sample.market_id == "m1"
        assert sample.question == "Will it rain?"
        assert sample.category == "weather"
        assert sample.close_ts == 1717200000
        assert sample.yes_token == "tok_yes"
        assert sample.yes_won is True

    def test_equality(self):
        a = MarketSample("m1", "Q?", "cat", 100, "tok", True)
        b = MarketSample("m1", "Q?", "cat", 100, "tok", True)
        assert a == b

    def test_inequality(self):
        a = MarketSample("m1", "Q?", "cat", 100, "tok", True)
        b = MarketSample("m2", "Q?", "cat", 100, "tok", True)
        assert a != b
