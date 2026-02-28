# strategies/tier_c/s88_social_graph.py
"""
S88: Social Graph Analysis of Traders

Analyse the social graph of traders on Polymarket to identify
influential wallets whose trades predict price moves.  The scan
step collects all active markets; the analyze step is a placeholder
for graph-based signal extraction.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class SocialGraphAnalysis(BaseStrategy):
    name = "s88_social_graph"
    tier = "C"
    strategy_id = 88
    required_data = []

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Collect all active markets for social graph overlay."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
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

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: derive signal from social graph of traders."""
        influencer_direction = opportunity.metadata.get("influencer_direction")
        if influencer_direction is None:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        estimated_prob = opportunity.metadata.get("graph_estimated_prob")
        if estimated_prob is None:
            return None

        side = "buy" if influencer_direction > 0 else "sell"
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.35,
            strategy_name=self.name,
            metadata={"influencer_direction": influencer_direction},
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
