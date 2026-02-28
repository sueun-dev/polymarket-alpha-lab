# strategies/tier_c/s76_conditional_prob.py
"""
S76: Conditional Probability Chains

Identify sequences of related events and exploit mispriced conditional
probabilities.  If markets for A, B, and A|B all exist, check whether
P(A|B) * P(B) = P(A and B) is consistent with market prices.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ConditionalProbChains(BaseStrategy):
    name = "s76_conditional_prob"
    tier = "C"
    strategy_id = 76
    required_data = []

    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find related event sequences that may form conditional chains."""
        opportunities: List[Opportunity] = []
        questions = {m.condition_id: m for m in markets if m.active}
        for m in markets:
            if not m.active:
                continue
            q = m.question.lower()
            if "if " not in q and "given " not in q and "conditional" not in q:
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
        """Check if P(A|B) is mispriced relative to P(A), P(B).

        In production this would:
        1. Parse conditional relationship from question text
        2. Look up P(A) and P(B) from related markets
        3. Compute implied P(A|B) = P(A and B) / P(B)
        4. Compare to market price of the conditional market
        """
        implied_prob = opportunity.metadata.get("implied_conditional_prob")
        if implied_prob is None:
            return None
        edge = implied_prob - opportunity.market_price
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
            estimated_prob=implied_prob,
            market_price=opportunity.market_price,
            confidence=0.40,
            strategy_name=self.name,
            metadata={"implied_conditional_prob": implied_prob},
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
