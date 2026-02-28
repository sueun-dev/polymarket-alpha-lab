# strategies/tier_c/s79_exit_timing.py
"""
S79: Optimal Exit Timing

For markets where we already hold positions, calculate the optimal
exit point balancing time-decay gains against adverse-move risk.
Uses a simple expected-value framework: exit when marginal expected
gain from holding < marginal risk.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ExitTiming(BaseStrategy):
    name = "s79_exit_timing"
    tier = "C"
    strategy_id = 79
    required_data = ["positions"]

    EXIT_THRESHOLD = 0.03  # Exit when remaining edge < 3%

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets where we hold existing positions."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            position = self._get_position(m)
            if position is None:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "entry_price": position.get("entry_price"),
                    "size": position.get("size"),
                    "side": position.get("side", "buy"),
                },
            ))
        return opportunities

    def _get_position(self, market: Market) -> Optional[dict]:
        """Read position info from token metadata (placeholder).

        In production this would query a position-tracking service.
        """
        for t in market.tokens:
            if t.get("has_position"):
                return {
                    "entry_price": t.get("entry_price"),
                    "size": t.get("position_size"),
                    "side": t.get("position_side", "buy"),
                }
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Calculate optimal exit point for existing position.

        Exit when remaining edge (distance to resolution) is smaller
        than the risk of an adverse move.
        """
        entry_price = opportunity.metadata.get("entry_price")
        if entry_price is None:
            return None
        current = opportunity.market_price
        remaining_edge = abs(current - entry_price)
        # If position is profitable and remaining edge is thin, exit
        if current > entry_price and (1.0 - current) < self.EXIT_THRESHOLD:
            token_id = self._get_token_id(opportunity, "yes")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="sell",
                estimated_prob=current,
                market_price=current,
                confidence=0.60,
                strategy_name=self.name,
                metadata={
                    "entry_price": entry_price,
                    "remaining_edge": 1.0 - current,
                    "action": "exit",
                },
            )
        return None

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
