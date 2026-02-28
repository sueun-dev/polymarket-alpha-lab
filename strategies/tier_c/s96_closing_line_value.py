# strategies/tier_c/s96_closing_line_value.py
"""
S96: Closing Line Value Tracking

Track how prices evolve as markets approach resolution.  If your
entry price consistently beats the closing line (final price before
resolution), you have a measurable edge.  This strategy scans
markets near resolution and evaluates whether the current price
is below the expected closing line.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ClosingLineValue(BaseStrategy):
    name = "s96_closing_line_value"
    tier = "C"
    strategy_id = 96
    required_data = []

    MAX_DAYS_TO_RESOLUTION = 3
    MIN_CLV_EDGE = 0.03

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets near resolution (within 3 days)."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            days_left = self._days_to_resolution(m)
            if days_left is None or days_left > self.MAX_DAYS_TO_RESOLUTION:
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
                    "days_left": days_left,
                },
            ))
        return opportunities

    @staticmethod
    def _days_to_resolution(market: Market) -> Optional[float]:
        for t in market.tokens:
            dl = t.get("days_left")
            if dl is not None:
                return float(dl)
        return None

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """If entry beats expected closing line, trade."""
        expected_closing = opportunity.metadata.get("expected_closing_price")
        if expected_closing is None:
            return None

        clv = expected_closing - opportunity.market_price
        if clv < self.MIN_CLV_EDGE:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=expected_closing,
            market_price=opportunity.market_price,
            confidence=0.55,
            strategy_name=self.name,
            metadata={"clv": clv, "expected_closing": expected_closing},
        )

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        for t in opportunity.metadata.get("tokens", []):
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
