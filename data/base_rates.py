"""Category base-rate database for Polymarket prediction markets.

Most prediction-market questions resolve NO (status-quo bias).  This module
provides default and empirically-calibrated per-category NO resolution rates
that downstream strategies use as Bayesian priors.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.base_provider import BaseDataProvider
from data.historical_fetcher import MarketSample


class BaseRateProvider(BaseDataProvider):
    """Manages category-specific base rates for market resolution.

    Extends :class:`BaseDataProvider` with methods for computing, caching,
    and querying NO-resolution base rates by market category.
    """

    name = "base_rates"

    DEFAULT_RATES: Dict[str, Dict[str, Any]] = {
        "politics": {"no_rate": 0.95, "description": "Political events rarely happen as specified"},
        "crypto": {"no_rate": 0.70, "description": "Crypto price targets are moderately uncertain"},
        "geopolitical": {"no_rate": 0.85, "description": "Geopolitical events mostly don't happen"},
        "sports": {"no_rate": 0.50, "description": "Sports outcomes are roughly balanced"},
        "science": {"no_rate": 0.80, "description": "Scientific milestones rarely met on deadline"},
        "entertainment": {"no_rate": 0.75, "description": "Entertainment predictions moderately uncertain"},
        "economics": {"no_rate": 0.80, "description": "Economic thresholds rarely hit precisely"},
        "technology": {"no_rate": 0.75, "description": "Tech milestones moderately uncertain"},
        "weather": {"no_rate": 0.60, "description": "Weather events somewhat balanced"},
        "unknown": {"no_rate": 0.65, "description": "Default for uncategorized markets"},
    }

    CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "politics": [
            "president", "election", "senate", "congress", "democrat",
            "republican", "vote", "poll", "governor", "mayor", "biden", "trump",
        ],
        "crypto": [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "token", "defi",
            "blockchain", "solana", "dogecoin",
        ],
        "sports": [
            "nfl", "nba", "mlb", "soccer", "football", "basketball",
            "baseball", "championship", "super bowl", "world cup", "game",
            "match", "score",
        ],
        "weather": [
            "temperature", "weather", "rain", "snow", "hurricane", "storm",
            "flood", "heat", "cold", "wind",
        ],
        "geopolitical": [
            "war", "conflict", "nato", "china", "russia", "military",
            "sanctions", "invasion", "cease",
        ],
        "science": [
            "nasa", "space", "vaccine", "fda", "drug", "clinical", "study",
            "research", "discovery",
        ],
        "economics": [
            "gdp", "inflation", "fed", "interest rate", "unemployment",
            "recession", "market", "stock", "s&p",
        ],
        "technology": [
            "ai", "artificial intelligence", "apple", "google", "microsoft",
            "launch", "release",
        ],
        "entertainment": [
            "oscar", "grammy", "emmy", "movie", "film", "album", "show",
            "netflix", "disney",
        ],
    }

    # Minimum number of samples required for a category to be considered
    # statistically significant when computing empirical base rates.
    MIN_SAMPLES = 10

    def __init__(self, cache_dir: Path | None = None) -> None:
        super().__init__()
        self.cache_dir = cache_dir or Path("data/cache/")

    # ------------------------------------------------------------------
    # BaseDataProvider interface
    # ------------------------------------------------------------------

    def fetch(self, **kwargs: Any) -> Any:
        """Main entry point -- returns all current rates."""
        return self.get_all_rates()

    # ------------------------------------------------------------------
    # Rate look-ups
    # ------------------------------------------------------------------

    def get_no_rate(self, category: str) -> float:
        """Return the NO resolution rate for *category*.

        Category names are normalised to lowercase.  Falls back to the
        ``"unknown"`` rate when the category is not recognised.
        """
        rates = self.get_all_rates()
        key = category.lower()
        entry = rates.get(key)
        if entry is not None:
            return entry["no_rate"]
        return rates["unknown"]["no_rate"]

    def get_yes_rate(self, category: str) -> float:
        """Return the YES resolution rate for *category* (= 1.0 - NO rate)."""
        return 1.0 - self.get_no_rate(category)

    # ------------------------------------------------------------------
    # Empirical rate computation
    # ------------------------------------------------------------------

    def build_from_historical(self, samples: List[MarketSample]) -> dict:
        """Compute empirical base rates from historical market data.

        Groups *samples* by category, computes the NO rate for each
        category that has at least :attr:`MIN_SAMPLES` data points, and
        merges the result with :attr:`DEFAULT_RATES`.  Empirical values
        override defaults when available.

        The merged rates are written to the JSON cache file and returned.
        """
        # Group by category
        buckets: Dict[str, List[bool]] = {}
        for s in samples:
            cat = s.category.lower()
            buckets.setdefault(cat, []).append(s.yes_won)

        empirical: Dict[str, Dict[str, Any]] = {}
        for cat, outcomes in buckets.items():
            if len(outcomes) < self.MIN_SAMPLES:
                continue
            no_count = sum(1 for won in outcomes if not won)
            no_rate = round(no_count / len(outcomes), 4)
            empirical[cat] = {
                "no_rate": no_rate,
                "description": f"Empirical from {len(outcomes)} samples",
            }

        # Merge: defaults as base, empirical overrides
        merged = {k: dict(v) for k, v in self.DEFAULT_RATES.items()}
        for cat, data in empirical.items():
            merged[cat] = data

        # Persist to cache
        cache_path = self.cache_dir / "base_rates.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(merged, indent=2))

        return merged

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def load_from_cache(self) -> Optional[dict]:
        """Load rates from the JSON cache file, or return ``None``."""
        cache_path = self.cache_dir / "base_rates.json"
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text())
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return None

    def get_all_rates(self) -> dict:
        """Return current rates -- cached if available, else defaults."""
        cached = self.load_from_cache()
        if cached is not None:
            return cached
        return {k: dict(v) for k, v in self.DEFAULT_RATES.items()}

    # ------------------------------------------------------------------
    # Question categorisation
    # ------------------------------------------------------------------

    def categorize_question(self, question: str) -> str:
        """Classify a market question into a category using keyword matching.

        Returns the first category whose keyword list has a match in the
        lowercased *question*.  Returns ``"unknown"`` when nothing matches.
        """
        q_lower = question.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in q_lower:
                    return category
        return "unknown"
