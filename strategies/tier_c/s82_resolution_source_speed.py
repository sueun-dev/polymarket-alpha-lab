# strategies/tier_c/s82_resolution_source_speed.py
"""
S82: Resolution Source Speed Ranking

Rank markets by how quickly their resolution source publishes results.
Prioritize trading in markets where you can verify the outcome before
the market fully reprices (e.g. AP calls elections faster than the
official count).
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

FAST_SOURCES = ["ap", "reuters", "associated press", "official api", "live feed"]


class ResolutionSourceSpeed(BaseStrategy):
    name = "s82_resolution_source_speed"
    tier = "C"
    strategy_id = 82
    required_data = []

    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with fast-updating resolution sources."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            text = (m.question + " " + m.description).lower()
            if not any(src in text for src in FAST_SOURCES):
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Prioritize markets where resolution source is fastest.

        In production this would:
        1. Rank resolution sources by historical publish speed
        2. Monitor the source for early resolution signals
        3. Trade before the market fully incorporates the result
        """
        source_prob = opportunity.metadata.get("source_estimated_prob")
        if source_prob is None:
            return None
        edge = source_prob - opportunity.market_price
        if abs(edge) < self.MIN_EDGE:
            return None
        side = "buy" if edge > 0 else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=source_prob,
            market_price=opportunity.market_price,
            confidence=0.50,
            strategy_name=self.name,
            metadata={"source_estimated_prob": source_prob},
        )

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
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
