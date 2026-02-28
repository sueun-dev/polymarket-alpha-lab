# strategies/tier_b/s47_parallel_market_monitor.py
"""
S47: Parallel Market Monitor

Monitor related markets simultaneously and detect cross-market
divergences. Markets in the same category (e.g. multiple elections,
multiple crypto price milestones) should move in correlated ways.
When one diverges from the group, it signals a potential mispricing.
"""
from collections import defaultdict
from typing import Dict, List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ParallelMarketMonitor(BaseStrategy):
    name = "s47_parallel_market_monitor"
    tier = "B"
    strategy_id = 47
    required_data = []

    DIVERGENCE_THRESHOLD = 0.15  # Flag if price differs from group avg by this much
    CONFIDENCE = 0.55
    MIN_GROUP_SIZE = 2  # Need at least 2 markets in a category

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Group markets by category and flag divergent ones."""
        # Group active markets by category
        groups: Dict[str, list] = defaultdict(list)
        for m in markets:
            if not m.active:
                continue
            if not m.category:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            groups[m.category].append((m, yes_price))

        opportunities = []
        for category, group in groups.items():
            if len(group) < self.MIN_GROUP_SIZE:
                continue
            avg_price = sum(p for _, p in group) / len(group)
            for m, yes_price in group:
                divergence = yes_price - avg_price
                if abs(divergence) < self.DIVERGENCE_THRESHOLD:
                    continue
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=category,
                    metadata={
                        "tokens": m.tokens,
                        "group_avg_price": round(avg_price, 4),
                        "divergence": round(divergence, 4),
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
        """Cross-market divergence detection.

        If a market's price is above the group average, it may be overpriced
        -> buy NO. If below, it may be underpriced -> buy YES.
        """
        divergence = opportunity.metadata.get("divergence", 0)
        tokens = opportunity.metadata.get("tokens", [])
        group_avg = opportunity.metadata.get("group_avg_price", 0.50)

        if divergence > 0:
            # Overpriced relative to group -> buy NO (mean revert)
            token_id = self._find_token(tokens, "no")
            estimated_prob = 1.0 - group_avg
            market_price = 1.0 - opportunity.market_price
        else:
            # Underpriced relative to group -> buy YES (mean revert)
            token_id = self._find_token(tokens, "yes")
            estimated_prob = group_avg
            market_price = opportunity.market_price

        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=market_price,
            confidence=self.CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "divergence": divergence,
                "group_avg": group_avg,
            },
        )

    @staticmethod
    def _find_token(tokens: list, outcome: str) -> Optional[str]:
        for t in tokens:
            if t.get("outcome", "").lower() == outcome:
                return t.get("token_id", "")
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
