# strategies/tier_s/s03_nothing_ever_happens.py
"""
S03: Nothing Ever Happens

Systematically bet NO on dramatic outcome markets. ~70% of Polymarket
markets resolve to NO. Market overestimates probability of dramatic change.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class NothingEverHappens(BaseStrategy):
    name = "s03_nothing_ever_happens"
    tier = "S"
    strategy_id = 3
    required_data = []

    DRAMATIC_KEYWORDS = [
        "war", "invade", "invasion", "crash", "collapse", "impeach", "resign",
        "fire", "default", "ban", "destroy", "overthrow", "assassin",
    ]
    MIN_YES_PRICE = 0.15  # Don't bet on already-low markets
    MAX_YES_PRICE = 0.70  # Don't bet against near-certainties
    BASE_NO_RATE = 0.70   # 70% of markets resolve NO

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            q_lower = m.question.lower()
            is_dramatic = any(kw in q_lower for kw in self.DRAMATIC_KEYWORDS)
            if not is_dramatic:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price and self.MIN_YES_PRICE < yes_price < self.MAX_YES_PRICE:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={"tokens": m.tokens},
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        yes_price = opportunity.market_price

        # NO probability estimate based on base rate
        estimated_no_prob = self.BASE_NO_RATE
        no_price = 1 - yes_price
        edge = round(estimated_no_prob - no_price, 10)

        if edge < 0.05:
            return None

        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",
            estimated_prob=estimated_no_prob,
            market_price=no_price,
            confidence=0.65,
            strategy_name=self.name,
        )

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
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
