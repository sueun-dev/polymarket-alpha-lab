# strategies/tier_c/s71_kaito_attention.py
"""
S71: Kaito AI Attention Markets

Trade markets based on AI mindshare and attention metrics from Kaito.
Scan for markets mentioning kaito, attention, or mindshare keywords,
then use attention-flow data to estimate probability adjustments.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class KaitoAttention(BaseStrategy):
    name = "s71_kaito_attention"
    tier = "C"
    strategy_id = 71
    required_data = ["kaito_api"]

    KEYWORDS = ["kaito", "attention", "mindshare"]
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets related to AI attention/mindshare on Kaito."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q = m.question.lower()
            if not any(kw in q for kw in self.KEYWORDS):
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
        """Placeholder: requires Kaito API for attention scoring.

        In production this would:
        1. Query Kaito for current mindshare metrics
        2. Compare attention trends to market pricing
        3. Identify mispriced attention-driven markets
        """
        attention_score = opportunity.metadata.get("attention_score")
        if attention_score is None:
            return None
        edge = attention_score - opportunity.market_price
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
            estimated_prob=attention_score,
            market_price=opportunity.market_price,
            confidence=0.35,
            strategy_name=self.name,
            metadata={"attention_score": attention_score},
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
