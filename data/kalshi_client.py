"""Kalshi market data provider for cross-platform arbitrage analysis."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json

# Stop words removed during fuzzy matching to focus on meaningful tokens.
_STOP_WORDS: Set[str] = frozenset({
    "the", "a", "an", "is", "will", "be", "to", "in", "on", "at", "of",
    "for", "by", "and", "or", "this", "that", "it", "its", "are", "was",
    "were", "been", "being", "have", "has", "had", "do", "does", "did",
    "but", "if", "not", "no", "so", "up", "out", "about", "into", "with",
    "from", "than", "too", "very", "can", "could", "would", "should",
    "shall", "may", "might", "must", "need", "before", "after", "during",
    "above", "below", "between", "each", "every", "all", "any", "both",
    "few", "more", "most", "other", "some", "such", "only", "own", "same",
    "then", "there", "here", "when", "where", "why", "how", "what", "which",
    "who", "whom", "whose",
})

# Pattern used to tokenize text into alphanumeric words (preserving numbers).
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


class KalshiDataProvider(BaseDataProvider):
    """Read-only Kalshi market data for cross-platform arbitrage detection.

    Uses the Kalshi public trade API (no authentication required for market
    data endpoints).  All HTTP calls go through :func:`http_get_json` which
    provides retry / backoff behaviour.
    """

    name: str = "kalshi"

    BASE_URL: str = "https://api.elections.kalshi.com/trade-api/v2"

    # Cache TTLs in seconds.
    _MARKETS_TTL: float = 60.0
    _ORDERBOOK_TTL: float = 10.0

    # ------------------------------------------------------------------
    # BaseDataProvider interface
    # ------------------------------------------------------------------

    def fetch(self, **kwargs: Any) -> Any:
        """Dispatch to the appropriate method based on *kwargs*.

        Supported keyword arguments:

        * ``action="markets"``  -- delegates to :meth:`get_markets`
        * ``action="orderbook", ticker=<str>`` -- delegates to :meth:`get_market_orderbook`
        * ``action="match", question=<str>, markets=<list>`` -- delegates to
          :meth:`match_polymarket_to_kalshi`
        * ``action="arb_edge", poly_yes=<float>, kalshi_yes=<float>`` --
          delegates to :meth:`compute_arb_edge`
        """
        action = kwargs.get("action", "markets")

        if action == "markets":
            return self.get_markets(
                limit=kwargs.get("limit", 100),
                status=kwargs.get("status", "open"),
            )

        if action == "orderbook":
            ticker = kwargs.get("ticker")
            if not ticker:
                self.logger.warning("fetch(action='orderbook') missing 'ticker'")
                return None
            return self.get_market_orderbook(ticker)

        if action == "match":
            question = kwargs.get("question", "")
            markets = kwargs.get("markets", [])
            return self.match_polymarket_to_kalshi(question, markets)

        if action == "arb_edge":
            poly_yes = kwargs.get("poly_yes", 0.0)
            kalshi_yes = kwargs.get("kalshi_yes", 0.0)
            return self.compute_arb_edge(
                poly_yes,
                kalshi_yes,
                poly_fee=kwargs.get("poly_fee", 0.01),
                kalshi_fee=kwargs.get("kalshi_fee", 0.07),
            )

        self.logger.warning("fetch() unknown action: %s", action)
        return None

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_markets(self, limit: int = 100, status: str = "open") -> List[dict]:
        """Return a list of Kalshi markets.

        Results are cached for 60 seconds.
        """
        cache_key = f"markets:{limit}:{status}"
        cached = self.get_cached(cache_key, ttl=self._MARKETS_TTL)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/markets?limit={limit}&status={status}"
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.exception("Failed to fetch Kalshi markets")
            return []

        markets: List[dict] = []
        if isinstance(data, dict):
            markets = data.get("markets", [])
        elif isinstance(data, list):
            markets = data

        self.set_cached(cache_key, markets)
        return markets

    def get_market_orderbook(self, ticker: str) -> Optional[dict]:
        """Return the order-book for a single Kalshi market *ticker*.

        Results are cached for 10 seconds.
        """
        cache_key = f"orderbook:{ticker}"
        cached = self.get_cached(cache_key, ttl=self._ORDERBOOK_TTL)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/markets/{ticker}/orderbook"
        try:
            data = http_get_json(url)
        except Exception:
            self.logger.exception("Failed to fetch orderbook for %s", ticker)
            return None

        if not isinstance(data, dict):
            return None

        result: Dict[str, Any] = {
            "yes": data.get("yes", []),
            "no": data.get("no", []),
        }

        self.set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Fuzzy matching
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Lowercase, tokenize, and remove stop words."""
        return [
            tok for tok in _TOKEN_RE.findall(text.lower())
            if tok not in _STOP_WORDS
        ]

    def match_polymarket_to_kalshi(
        self,
        polymarket_question: str,
        kalshi_markets: List[dict],
    ) -> Optional[dict]:
        """Find the best Kalshi market matching *polymarket_question*.

        Uses simple word-overlap scoring after stop-word removal.  Returns
        ``None`` when no market exceeds a similarity threshold of 0.3.
        """
        if not polymarket_question or not kalshi_markets:
            return None

        poly_tokens = self._tokenize(polymarket_question)
        if not poly_tokens:
            return None

        best_score: float = 0.0
        best_market: Optional[dict] = None

        for market in kalshi_markets:
            # Build the Kalshi text from title and subtitle.
            kalshi_text = " ".join(
                filter(None, [market.get("title", ""), market.get("subtitle", "")])
            )
            kalshi_tokens = self._tokenize(kalshi_text)
            if not kalshi_tokens:
                continue

            overlap = len(set(poly_tokens) & set(kalshi_tokens))
            denominator = max(len(set(poly_tokens)), len(set(kalshi_tokens)))
            score = overlap / denominator if denominator else 0.0

            if score > best_score:
                best_score = score
                best_market = market

        if best_score > 0.3:
            return best_market
        return None

    # ------------------------------------------------------------------
    # Arbitrage edge computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_arb_edge(
        poly_yes_price: float,
        kalshi_yes_price: float,
        poly_fee: float = 0.01,
        kalshi_fee: float = 0.07,
    ) -> dict:
        """Compute fee-adjusted arbitrage edge between Polymarket and Kalshi.

        Returns a dict with effective prices, both directional edges, the
        best edge, and the recommended direction.
        """
        poly_yes_effective = poly_yes_price * (1 + poly_fee)
        kalshi_yes_effective = kalshi_yes_price * (1 + kalshi_fee)

        buy_poly_sell_kalshi = (
            kalshi_yes_price * (1 - kalshi_fee)
            - poly_yes_price * (1 + poly_fee)
        )
        buy_kalshi_sell_poly = (
            poly_yes_price * (1 - poly_fee)
            - kalshi_yes_price * (1 + kalshi_fee)
        )

        if buy_poly_sell_kalshi >= buy_kalshi_sell_poly:
            best_edge = buy_poly_sell_kalshi
            direction = "buy_poly"
        else:
            best_edge = buy_kalshi_sell_poly
            direction = "buy_kalshi"

        return {
            "poly_yes_effective": poly_yes_effective,
            "kalshi_yes_effective": kalshi_yes_effective,
            "buy_poly_sell_kalshi": buy_poly_sell_kalshi,
            "buy_kalshi_sell_poly": buy_kalshi_sell_poly,
            "best_edge": best_edge,
            "direction": direction,
        }
