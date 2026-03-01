"""News data provider using GNews API with keyword-based sentiment scoring."""
from __future__ import annotations

import datetime as dt
import os
import re
from typing import Any, Dict, List, Optional

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

# ---------------------------------------------------------------------------
# Sentiment keyword lists
# ---------------------------------------------------------------------------

POSITIVE_KEYWORDS: List[str] = [
    "surge", "soar", "jump", "gain", "rise", "rally", "boost", "win",
    "victory", "success", "approve", "pass", "confirm", "strong", "record",
    "high", "up", "positive", "growth", "increase", "breakthrough", "deal",
]

NEGATIVE_KEYWORDS: List[str] = [
    "crash", "fall", "drop", "decline", "loss", "plunge", "fail", "reject",
    "deny", "weak", "low", "down", "negative", "cut", "collapse", "crisis",
    "concern", "worry", "threat", "risk", "scandal", "controversy",
]

# Common filler words to strip from market questions when building search queries.
_STOP_WORDS: set[str] = {
    "will", "the", "be", "by", "in", "on", "a", "an", "to", "of",
    "for", "is", "at", "this", "that", "it",
}

_GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"


class NewsDataProvider(BaseDataProvider):
    """Fetches news articles from GNews and computes simple sentiment scores.

    If no API key is configured via ``NEWS_API_KEY`` or ``GNEWS_API_KEY``
    environment variables, every public method silently returns ``None``
    instead of raising.
    """

    name: str = "news"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: Optional[str] = (
            os.environ.get("NEWS_API_KEY") or os.environ.get("GNEWS_API_KEY") or None
        )

    # ------------------------------------------------------------------
    # BaseDataProvider interface
    # ------------------------------------------------------------------

    def fetch(self, **kwargs: Any) -> Any:
        """Delegates to :meth:`search_news`."""
        query: str = kwargs.get("query", kwargs.get("q", ""))
        if not query:
            return None
        return self.search_news(
            query=query,
            max_results=kwargs.get("max_results", 10),
            lang=kwargs.get("lang", "en"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_news(
        self,
        query: str,
        max_results: int = 10,
        lang: str = "en",
    ) -> Optional[List[dict]]:
        """Search GNews for *query* and return a list of article dicts.

        Results are cached for 300 seconds (5 minutes).
        Returns ``None`` when no API key is available.
        """
        if not self._api_key:
            return None

        cache_key = f"search:{query}:{max_results}:{lang}"
        cached = self.get_cached(cache_key, ttl=300.0)
        if cached is not None:
            return cached  # type: ignore[return-value]

        url = (
            f"{_GNEWS_SEARCH_URL}"
            f"?q={_url_encode(query)}"
            f"&max={max_results}"
            f"&lang={lang}"
            f"&apikey={self._api_key}"
        )

        try:
            data = http_get_json(url)
        except Exception:
            self.logger.warning("GNews search failed for query=%r", query, exc_info=True)
            return None

        if not isinstance(data, dict):
            return None

        articles: List[dict] = data.get("articles", [])  # type: ignore[union-attr]
        self.set_cached(cache_key, articles)
        return articles

    # ------------------------------------------------------------------

    @staticmethod
    def sentiment_score(text: str) -> float:
        """Return a keyword-based sentiment score in ``[-1.0, 1.0]``.

        The score is ``(positive_count - negative_count) / max(total, 1)``
        where *total* is the sum of positive and negative keyword hits,
        counted via case-insensitive whole-word matching.
        """
        if not text:
            return 0.0

        lower = text.lower()
        words = re.findall(r"[a-z]+", lower)

        pos_count = sum(1 for w in words if w in _POS_SET)
        neg_count = sum(1 for w in words if w in _NEG_SET)
        total = pos_count + neg_count
        if total == 0:
            return 0.0

        score = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, score))

    # ------------------------------------------------------------------

    def get_sentiment_for_market(
        self,
        question: str,
        max_articles: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Fetch recent news for *question* and return aggregate sentiment.

        Returns a dict with ``avg_sentiment``, ``article_count``, and
        ``articles``, or ``None`` when the API key is missing or the
        search fails.
        """
        if not self._api_key:
            return None

        search_terms = self._extract_search_terms(question)
        articles = self.search_news(search_terms, max_results=max_articles)
        if articles is None:
            return None

        sentiments: List[float] = []
        for article in articles:
            combined = " ".join(
                filter(None, [article.get("title", ""), article.get("description", "")])
            )
            sentiments.append(self.sentiment_score(combined))

        avg = sum(sentiments) / len(sentiments) if sentiments else 0.0

        return {
            "avg_sentiment": avg,
            "article_count": len(articles),
            "articles": articles,
        }

    # ------------------------------------------------------------------

    def has_recent_event(
        self,
        query: str,
        hours: int = 24,
    ) -> Optional[bool]:
        """Check whether any news article for *query* was published recently.

        Returns ``True`` if at least one article appeared within the last
        *hours* hours, ``False`` if none did, or ``None`` when the API
        key is missing or the search fails.
        """
        if not self._api_key:
            return None

        articles = self.search_news(query)
        if articles is None:
            return None

        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)

        for article in articles:
            published = article.get("publishedAt")
            if not published:
                continue
            try:
                pub_dt = dt.datetime.fromisoformat(
                    str(published).replace("Z", "+00:00")
                )
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=dt.timezone.utc)
                if pub_dt >= cutoff:
                    return True
            except (ValueError, TypeError):
                continue

        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_search_terms(question: str) -> str:
        """Reduce a market question to a compact search query.

        Strips common filler/stop words, keeps the first 5 meaningful
        tokens, and joins them with spaces.
        """
        words = re.findall(r"[A-Za-z0-9]+", question)
        meaningful = [w for w in words if w.lower() not in _STOP_WORDS]
        return " ".join(meaningful[:5])


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_POS_SET: frozenset[str] = frozenset(POSITIVE_KEYWORDS)
_NEG_SET: frozenset[str] = frozenset(NEGATIVE_KEYWORDS)


def _url_encode(value: str) -> str:
    """Minimal percent-encoding for a query-string value."""
    import urllib.parse
    return urllib.parse.quote_plus(value)
