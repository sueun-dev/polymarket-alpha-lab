# strategies/tier_c/s91_dispute_monitoring.py
"""
S91: UMA Dispute Monitoring

Monitor UMA's optimistic oracle for active disputes on Polymarket
resolution proposals.  When a dispute is raised the market often
misprice the probability of the dispute succeeding -- trade based
on the likely dispute outcome.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class DisputeMonitoring(BaseStrategy):
    name = "s91_dispute_monitoring"
    tier = "C"
    strategy_id = 91
    required_data = []

    DISPUTE_KEYWORDS = ["dispute", "uma", "challenged", "oracle"]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with active disputes."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if not self._has_active_dispute(m):
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "has_dispute": True},
            ))
        return opportunities

    def _has_active_dispute(self, market: Market) -> bool:
        """Check if market description or metadata mentions an active dispute."""
        desc = market.description.lower()
        return any(kw in desc for kw in self.DISPUTE_KEYWORDS)

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Trade based on dispute outcome probability."""
        dispute_success_prob = opportunity.metadata.get("dispute_success_prob")
        if dispute_success_prob is None:
            return None

        # If dispute likely succeeds, the original resolution was wrong
        # meaning current price is mispriced
        estimated_prob = 1.0 - opportunity.market_price if dispute_success_prob > 0.5 else opportunity.market_price
        edge = abs(estimated_prob - opportunity.market_price)
        if edge < 0.05:
            return None

        side = "buy" if estimated_prob > opportunity.market_price else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.45,
            strategy_name=self.name,
            metadata={"dispute_success_prob": dispute_success_prob},
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
