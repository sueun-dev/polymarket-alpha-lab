# strategies/tier_a/s23_correlated_lag.py
"""
S23: Correlated Asset Lag

After a primary event resolves (e.g. "Fed raises rates"), related markets
("Will mortgage rates rise?", "Will housing starts fall?") are slow to
reprice. This strategy identifies same-category markets and trades
the lagging ones once the primary event outcome is known.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CorrelatedLag(BaseStrategy):
    name = "s23_correlated_lag"
    tier = "A"
    strategy_id = 23
    required_data = []

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets in the same category that may be correlated."""
        category_buckets: dict[str, List[Market]] = {}
        for m in markets:
            if not m.active or not m.category:
                continue
            category_buckets.setdefault(m.category, []).append(m)

        opportunities: List[Opportunity] = []
        for category, group in category_buckets.items():
            if len(group) < 2:
                continue
            for m in group:
                yes_price = self._get_yes_price(m)
                if yes_price is None:
                    continue
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=category,
                    metadata={
                        "tokens": m.tokens,
                        "group_size": len(group),
                    },
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder -- requires event correlation mapping to detect lag."""
        # In production: detect when a primary market in the same category
        # has recently resolved, then compare the correlated market's price
        # to its expected fair value given the primary outcome.
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=size,
            strategy_name=self.name,
        )
