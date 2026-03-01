"""Feature engine for momentum / volatility analysis of Polymarket prices."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from data.base_provider import BaseDataProvider
from data.historical_fetcher import HistoricalFetcher, MarketSample

HORIZONS_MIN: Tuple[int, ...] = (5, 10, 15, 30, 60, 120)


@dataclass
class FeatureRow:
    """A single feature observation at a given horizon before market close."""

    market_id: str
    close_ts: int
    horizon_m: int
    category: str
    p: float
    p_minus_5m: float
    p_minus_15m: float
    p_minus_60m: float
    mom5: float
    mom15: float
    mom60: float
    range60: float
    std60: float
    dist_mid: float
    yes_won: bool


def build_feature_rows(
    sample: MarketSample, history: Sequence[Tuple[int, float]]
) -> List[FeatureRow]:
    """Build feature rows for every horizon in *HORIZONS_MIN*.

    For each horizon the function computes entry-time prices, momentum
    indicators, volatility (population stdev), and price range over the
    preceding 60 minutes.  Horizons with insufficient or out-of-range data
    are silently skipped.
    """
    rows: List[FeatureRow] = []

    for m in HORIZONS_MIN:
        entry_ts = sample.close_ts - m * 60

        p = HistoricalFetcher.price_at_or_before(history, entry_ts)
        p5 = HistoricalFetcher.price_at_or_before(history, entry_ts - 5 * 60)
        p15 = HistoricalFetcher.price_at_or_before(history, entry_ts - 15 * 60)
        p60 = HistoricalFetcher.price_at_or_before(history, entry_ts - 60 * 60)
        if p is None or p5 is None or p15 is None or p60 is None:
            continue
        if not (0 <= p <= 1 and 0 <= p5 <= 1 and 0 <= p15 <= 1 and 0 <= p60 <= 1):
            continue

        win = HistoricalFetcher.window_prices(history, entry_ts - 60 * 60, entry_ts)
        if len(win) < 4:
            continue

        rng = max(win) - min(win)
        std = statistics.pstdev(win) if len(win) > 1 else 0.0

        rows.append(
            FeatureRow(
                market_id=sample.market_id,
                close_ts=sample.close_ts,
                horizon_m=m,
                category=sample.category,
                p=p,
                p_minus_5m=p5,
                p_minus_15m=p15,
                p_minus_60m=p60,
                mom5=p - p5,
                mom15=p - p15,
                mom60=p - p60,
                range60=rng,
                std60=std,
                dist_mid=abs(p - 0.5),
                yes_won=sample.yes_won,
            )
        )

    return rows


class LiveFeatureBuilder(BaseDataProvider):
    """Compute live momentum / volatility features from recent CLOB prices.

    Mirrors the feature logic of :func:`build_feature_rows` but operates on
    a live price stream rather than historical market data.
    """

    name = "feature_engine"

    def fetch(self, **kwargs: Any) -> Any:
        """Main entry point -- delegates to :meth:`compute_live_features`.

        Expected keyword arguments:

        * ``prices`` -- recent CLOB price history as ``List[Tuple[int, float]]``
        * ``current_ts`` -- Unix timestamp (seconds) of the current moment
        """
        prices: List[Tuple[int, float]] = kwargs.get("prices", [])
        current_ts: int = kwargs.get("current_ts", 0)
        return self.compute_live_features(prices, current_ts)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def compute_live_features(
        self, prices: List[Tuple[int, float]], current_ts: int
    ) -> Optional[Dict[str, float]]:
        """Compute momentum / volatility features for a live market.

        Returns a dict with keys ``p``, ``mom5``, ``mom15``, ``mom60``,
        ``range60``, ``std60``, and ``dist_mid``.  Returns ``None`` when
        there is insufficient price data to compute all features.
        """
        p = HistoricalFetcher.price_at_or_before(prices, current_ts)
        if p is None:
            return None

        mom5 = self.compute_momentum(prices, current_ts, 5)
        mom15 = self.compute_momentum(prices, current_ts, 15)
        mom60 = self.compute_momentum(prices, current_ts, 60)
        if mom5 is None or mom15 is None or mom60 is None:
            return None

        vol = self.compute_volatility(prices, current_ts, 60)
        if vol is None:
            return None

        win = HistoricalFetcher.window_prices(
            prices, current_ts - 60 * 60, current_ts
        )
        if len(win) < 4:
            return None

        rng = max(win) - min(win)

        return {
            "p": p,
            "mom5": mom5,
            "mom15": mom15,
            "mom60": mom60,
            "range60": rng,
            "std60": vol,
            "dist_mid": abs(p - 0.5),
        }

    def compute_momentum(
        self,
        prices: List[Tuple[int, float]],
        current_ts: int,
        lookback_minutes: int,
    ) -> Optional[float]:
        """Return *price_now - price_lookback* or ``None`` if data is missing."""
        p_now = HistoricalFetcher.price_at_or_before(prices, current_ts)
        p_past = HistoricalFetcher.price_at_or_before(
            prices, current_ts - lookback_minutes * 60
        )
        if p_now is None or p_past is None:
            return None
        return p_now - p_past

    def compute_volatility(
        self,
        prices: List[Tuple[int, float]],
        current_ts: int,
        window_minutes: int = 60,
    ) -> Optional[float]:
        """Return the population standard deviation of prices in the window.

        Returns ``None`` when fewer than 2 prices are available.
        """
        win = HistoricalFetcher.window_prices(
            prices, current_ts - window_minutes * 60, current_ts
        )
        if len(win) < 2:
            return None
        return statistics.pstdev(win)
