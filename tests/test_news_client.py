"""Tests for data.news_client -- NewsDataProvider."""
from __future__ import annotations

import datetime as dt
import time
from typing import Any, List
from unittest import mock

import pytest

from data.news_client import NewsDataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(
    title: str = "Test Article",
    description: str = "A test description",
    content: str = "Full article content here.",
    url: str = "https://example.com/article",
    published_at: str = "2026-02-28T10:00:00Z",
    source_name: str = "Test Source",
    source_url: str = "https://example.com",
) -> dict:
    """Build a realistic GNews article dict."""
    return {
        "title": title,
        "description": description,
        "content": content,
        "url": url,
        "publishedAt": published_at,
        "source": {"name": source_name, "url": source_url},
    }


def _gnews_response(articles: List[dict]) -> dict:
    """Wrap articles in the GNews API envelope."""
    return {"totalArticles": len(articles), "articles": articles}


def _provider_with_key(key: str = "test-api-key-123") -> NewsDataProvider:
    """Return a NewsDataProvider that has an API key set."""
    with mock.patch.dict("os.environ", {"NEWS_API_KEY": key}):
        return NewsDataProvider()


def _provider_without_key() -> NewsDataProvider:
    """Return a NewsDataProvider with no API key."""
    with mock.patch.dict("os.environ", {}, clear=True):
        # Ensure neither key env var is present
        env = {k: v for k, v in __import__("os").environ.items()
               if k not in ("NEWS_API_KEY", "GNEWS_API_KEY")}
        with mock.patch.dict("os.environ", env, clear=True):
            return NewsDataProvider()


# ===========================================================================
# sentiment_score
# ===========================================================================


class TestSentimentScore:
    """Unit tests for the static sentiment_score method."""

    def test_pure_positive(self):
        score = NewsDataProvider.sentiment_score("surge rally boost win victory")
        assert score > 0
        assert score == pytest.approx(1.0)

    def test_pure_negative(self):
        score = NewsDataProvider.sentiment_score("crash fall plunge decline loss")
        assert score < 0
        assert score == pytest.approx(-1.0)

    def test_mixed_text_near_zero(self):
        score = NewsDataProvider.sentiment_score("surge crash rally plunge")
        assert -0.1 <= score <= 0.1

    def test_empty_text_returns_zero(self):
        assert NewsDataProvider.sentiment_score("") == 0.0

    def test_no_keywords_returns_zero(self):
        assert NewsDataProvider.sentiment_score("the quick brown fox jumps") == 0.0

    def test_case_insensitive(self):
        score = NewsDataProvider.sentiment_score("SURGE RALLY BOOST")
        assert score > 0
        assert score == pytest.approx(1.0)

    def test_clamped_to_range(self):
        # Even with many positives, result never exceeds 1.0
        score = NewsDataProvider.sentiment_score(
            " ".join(["surge", "rally", "boost", "win", "gain", "rise", "jump"])
        )
        assert -1.0 <= score <= 1.0

    def test_single_positive_keyword(self):
        score = NewsDataProvider.sentiment_score("markets show strong performance")
        assert score > 0

    def test_single_negative_keyword(self):
        score = NewsDataProvider.sentiment_score("analysts express concern")
        assert score < 0

    def test_more_positive_than_negative(self):
        score = NewsDataProvider.sentiment_score("surge rally gain but some decline")
        assert score > 0

    def test_more_negative_than_positive(self):
        score = NewsDataProvider.sentiment_score("crash plunge collapse but some gain")
        assert score < 0

    def test_none_text_handled(self):
        # The type hint says str, but defensively check empty-ish input
        assert NewsDataProvider.sentiment_score("") == 0.0


# ===========================================================================
# _extract_search_terms
# ===========================================================================


class TestExtractSearchTerms:
    """Tests for the search-term extraction helper."""

    def test_removes_stop_words(self):
        result = NewsDataProvider._extract_search_terms(
            "Will the election be held in November"
        )
        words = result.lower().split()
        # "Will", "the", "be", "in" are stop words
        assert "will" not in words
        assert "the" not in words
        assert "be" not in words
        assert "in" not in words
        assert "election" in words

    def test_limits_to_five_words(self):
        result = NewsDataProvider._extract_search_terms(
            "Can Democrats win Georgia Senate race runoff election again"
        )
        words = result.split()
        assert len(words) <= 5

    def test_simple_question(self):
        result = NewsDataProvider._extract_search_terms("Will Bitcoin reach 100k")
        assert "Bitcoin" in result
        assert "reach" in result
        assert "100k" in result

    def test_empty_string(self):
        result = NewsDataProvider._extract_search_terms("")
        assert result == ""

    def test_all_stop_words(self):
        result = NewsDataProvider._extract_search_terms("Will the be in on a")
        assert result == ""

    def test_preserves_numbers(self):
        result = NewsDataProvider._extract_search_terms("Will GDP exceed 5 percent by 2026")
        assert "5" in result
        assert "GDP" in result

    def test_mixed_case_stop_words(self):
        result = NewsDataProvider._extract_search_terms("Is This The end")
        # "Is", "This", "The" should be removed
        assert "end" in result.lower()
        words = result.split()
        assert len(words) == 1


# ===========================================================================
# search_news
# ===========================================================================


class TestSearchNews:
    """Tests for the search_news method."""

    @mock.patch("data.news_client.http_get_json")
    def test_returns_articles_on_success(self, mock_http):
        articles = [_make_article(title="Article 1"), _make_article(title="Article 2")]
        mock_http.return_value = _gnews_response(articles)
        provider = _provider_with_key()

        result = provider.search_news("bitcoin")

        assert result is not None
        assert len(result) == 2
        assert result[0]["title"] == "Article 1"
        assert result[1]["title"] == "Article 2"
        mock_http.assert_called_once()
        # Verify URL contains the query and API key
        call_url = mock_http.call_args[0][0]
        assert "bitcoin" in call_url
        assert "test-api-key-123" in call_url

    @mock.patch("data.news_client.http_get_json")
    def test_caches_results(self, mock_http):
        articles = [_make_article()]
        mock_http.return_value = _gnews_response(articles)
        provider = _provider_with_key()

        result1 = provider.search_news("bitcoin")
        result2 = provider.search_news("bitcoin")

        assert result1 == result2
        # HTTP should be called only once due to caching
        assert mock_http.call_count == 1

    @mock.patch("data.news_client.http_get_json")
    def test_different_queries_not_cached_together(self, mock_http):
        mock_http.return_value = _gnews_response([_make_article()])
        provider = _provider_with_key()

        provider.search_news("bitcoin")
        provider.search_news("ethereum")

        assert mock_http.call_count == 2

    @mock.patch("data.news_client.http_get_json")
    def test_cache_expires(self, mock_http):
        mock_http.return_value = _gnews_response([_make_article()])
        provider = _provider_with_key()

        provider.search_news("bitcoin")

        # Backdate the cache entry beyond TTL (300 seconds)
        for key in list(provider._cache_ts):
            provider._cache_ts[key] = time.time() - 400

        provider.search_news("bitcoin")
        assert mock_http.call_count == 2

    def test_no_api_key_returns_none(self):
        provider = _provider_without_key()
        result = provider.search_news("bitcoin")
        assert result is None

    @mock.patch("data.news_client.http_get_json")
    def test_http_error_returns_none(self, mock_http):
        mock_http.side_effect = RuntimeError("network error")
        provider = _provider_with_key()

        result = provider.search_news("bitcoin")
        assert result is None

    @mock.patch("data.news_client.http_get_json")
    def test_empty_articles_list(self, mock_http):
        mock_http.return_value = _gnews_response([])
        provider = _provider_with_key()

        result = provider.search_news("obscure topic")
        assert result is not None
        assert result == []

    @mock.patch("data.news_client.http_get_json")
    def test_custom_params_in_url(self, mock_http):
        mock_http.return_value = _gnews_response([])
        provider = _provider_with_key()

        provider.search_news("test", max_results=3, lang="fr")

        call_url = mock_http.call_args[0][0]
        assert "max=3" in call_url
        assert "lang=fr" in call_url

    @mock.patch("data.news_client.http_get_json")
    def test_non_dict_response_returns_none(self, mock_http):
        mock_http.return_value = "not a dict"
        provider = _provider_with_key()

        result = provider.search_news("test")
        assert result is None


# ===========================================================================
# fetch (BaseDataProvider interface)
# ===========================================================================


class TestFetch:
    """Tests for the fetch() entry point."""

    @mock.patch("data.news_client.http_get_json")
    def test_delegates_to_search_news(self, mock_http):
        mock_http.return_value = _gnews_response([_make_article()])
        provider = _provider_with_key()

        result = provider.fetch(query="bitcoin")
        assert result is not None
        assert len(result) == 1

    def test_no_query_returns_none(self):
        provider = _provider_with_key()
        result = provider.fetch()
        assert result is None

    @mock.patch("data.news_client.http_get_json")
    def test_fetch_with_q_kwarg(self, mock_http):
        mock_http.return_value = _gnews_response([_make_article()])
        provider = _provider_with_key()

        result = provider.fetch(q="ethereum")
        assert result is not None

    def test_fetch_no_api_key(self):
        provider = _provider_without_key()
        result = provider.fetch(query="bitcoin")
        assert result is None


# ===========================================================================
# get_sentiment_for_market
# ===========================================================================


class TestGetSentimentForMarket:
    """Tests for market-level sentiment aggregation."""

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_returns_sentiment_dict(self, mock_search):
        mock_search.return_value = [
            _make_article(title="Stocks surge and rally", description="Markets gain"),
            _make_article(title="Prices rise sharply", description="Strong growth"),
        ]
        provider = _provider_with_key()

        result = provider.get_sentiment_for_market("Will stocks go up?")

        assert result is not None
        assert "avg_sentiment" in result
        assert "article_count" in result
        assert "articles" in result
        assert result["article_count"] == 2
        assert result["avg_sentiment"] > 0

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_negative_sentiment(self, mock_search):
        mock_search.return_value = [
            _make_article(title="Markets crash and plunge", description="Decline continues"),
        ]
        provider = _provider_with_key()

        result = provider.get_sentiment_for_market("Will markets recover?")

        assert result is not None
        assert result["avg_sentiment"] < 0

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_empty_articles_list(self, mock_search):
        mock_search.return_value = []
        provider = _provider_with_key()

        result = provider.get_sentiment_for_market("Will X happen?")

        assert result is not None
        assert result["avg_sentiment"] == 0.0
        assert result["article_count"] == 0

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_search_fails_returns_none(self, mock_search):
        mock_search.return_value = None
        provider = _provider_with_key()

        result = provider.get_sentiment_for_market("Will X happen?")
        assert result is None

    def test_no_api_key_returns_none(self):
        provider = _provider_without_key()
        result = provider.get_sentiment_for_market("Will X happen?")
        assert result is None

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_uses_extracted_search_terms(self, mock_search):
        mock_search.return_value = []
        provider = _provider_with_key()

        provider.get_sentiment_for_market("Will the President sign the bill?")

        # Verify search_news was called with extracted terms (not the full question)
        call_args = mock_search.call_args
        query = call_args[1].get("query", call_args[0][0] if call_args[0] else "")
        # "Will", "the" should be removed
        assert "Will" not in query.split()
        assert "the" not in query.split()

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_respects_max_articles_param(self, mock_search):
        mock_search.return_value = []
        provider = _provider_with_key()

        provider.get_sentiment_for_market("Test question", max_articles=3)

        call_kwargs = mock_search.call_args
        assert call_kwargs[1].get("max_results", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None) == 3


# ===========================================================================
# has_recent_event
# ===========================================================================


class TestHasRecentEvent:
    """Tests for the has_recent_event method."""

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_recent_article_returns_true(self, mock_search):
        # Article published 1 hour ago
        recent_time = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_search.return_value = [_make_article(published_at=recent_time)]

        provider = _provider_with_key()
        result = provider.has_recent_event("bitcoin crash")

        assert result is True

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_old_article_returns_false(self, mock_search):
        # Article published 48 hours ago
        old_time = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=48)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_search.return_value = [_make_article(published_at=old_time)]

        provider = _provider_with_key()
        result = provider.has_recent_event("bitcoin crash", hours=24)

        assert result is False

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_custom_hours_window(self, mock_search):
        # Article published 3 hours ago, window is 2 hours
        three_hours_ago = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_search.return_value = [_make_article(published_at=three_hours_ago)]

        provider = _provider_with_key()

        # Within 4 hours -> True
        assert provider.has_recent_event("test", hours=4) is True

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_custom_hours_window_too_narrow(self, mock_search):
        # Article published 3 hours ago, window is 2 hours
        three_hours_ago = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_search.return_value = [_make_article(published_at=three_hours_ago)]

        provider = _provider_with_key()

        # Within 2 hours -> False
        assert provider.has_recent_event("test", hours=2) is False

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_no_articles_returns_false(self, mock_search):
        mock_search.return_value = []
        provider = _provider_with_key()

        result = provider.has_recent_event("obscure topic")
        assert result is False

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_search_fails_returns_none(self, mock_search):
        mock_search.return_value = None
        provider = _provider_with_key()

        result = provider.has_recent_event("test")
        assert result is None

    def test_no_api_key_returns_none(self):
        provider = _provider_without_key()
        result = provider.has_recent_event("bitcoin")
        assert result is None

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_article_without_published_at_skipped(self, mock_search):
        article = _make_article()
        del article["publishedAt"]
        mock_search.return_value = [article]

        provider = _provider_with_key()
        result = provider.has_recent_event("test")

        assert result is False

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_article_with_invalid_date_skipped(self, mock_search):
        mock_search.return_value = [_make_article(published_at="not-a-date")]

        provider = _provider_with_key()
        result = provider.has_recent_event("test")

        assert result is False

    @mock.patch.object(NewsDataProvider, "search_news")
    def test_mixed_recent_and_old_articles(self, mock_search):
        recent_time = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        old_time = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=48)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_search.return_value = [
            _make_article(published_at=old_time),
            _make_article(published_at=recent_time),
        ]

        provider = _provider_with_key()
        result = provider.has_recent_event("bitcoin")

        assert result is True


# ===========================================================================
# Graceful degradation (no API key)
# ===========================================================================


class TestGracefulDegradation:
    """Verify that every public method returns None when no API key is set."""

    def test_search_news_returns_none(self):
        provider = _provider_without_key()
        assert provider.search_news("anything") is None

    def test_get_sentiment_for_market_returns_none(self):
        provider = _provider_without_key()
        assert provider.get_sentiment_for_market("Will X happen?") is None

    def test_has_recent_event_returns_none(self):
        provider = _provider_without_key()
        assert provider.has_recent_event("anything") is None

    def test_fetch_returns_none(self):
        provider = _provider_without_key()
        assert provider.fetch(query="anything") is None

    def test_gnews_api_key_env_var(self):
        """Verify GNEWS_API_KEY also works."""
        with mock.patch.dict("os.environ", {"GNEWS_API_KEY": "alt-key"}, clear=True):
            # Remove NEWS_API_KEY if present
            env = {k: v for k, v in __import__("os").environ.items()
                   if k != "NEWS_API_KEY"}
            with mock.patch.dict("os.environ", env, clear=True):
                # Re-add GNEWS_API_KEY since clear=True removes it
                with mock.patch.dict("os.environ", {"GNEWS_API_KEY": "alt-key"}):
                    provider = NewsDataProvider()
        assert provider._api_key == "alt-key"

    def test_news_api_key_takes_priority(self):
        """NEWS_API_KEY should be preferred over GNEWS_API_KEY."""
        with mock.patch.dict(
            "os.environ",
            {"NEWS_API_KEY": "primary-key", "GNEWS_API_KEY": "fallback-key"},
        ):
            provider = NewsDataProvider()
        assert provider._api_key == "primary-key"


# ===========================================================================
# Provider metadata
# ===========================================================================


class TestProviderMetadata:
    """Basic provider properties."""

    def test_name(self):
        provider = _provider_with_key()
        assert provider.name == "news"

    def test_logger_name(self):
        provider = _provider_with_key()
        assert provider.logger.name == "data.news"

    def test_inherits_base_data_provider(self):
        from data.base_provider import BaseDataProvider

        provider = _provider_with_key()
        assert isinstance(provider, BaseDataProvider)
