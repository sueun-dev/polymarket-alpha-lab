# strategies/tier_s/s05_negrisk_rebalancing.py
"""
S05: NegRisk Rebalancing

In multi-outcome markets (3+ options), if sum of all YES prices > $1.00,
buy NO on overpriced outcomes for risk-free profit.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class NegRiskRebalancing(BaseStrategy):
    name = "s05_negrisk_rebalancing"
    tier = "S"
    strategy_id = 5
    required_data = []

    MIN_OUTCOMES = 3
    MIN_OVERPRICE = 0.02  # 2% over $1.00

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            if len(m.tokens) >= self.MIN_OUTCOMES:
                total_yes = sum(float(t.get("price", 0)) for t in m.tokens)
                if total_yes > 1.0 + self.MIN_OVERPRICE:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id,
                        question=m.question,
                        market_price=total_yes,
                        category=m.category,
                        metadata={
                            "tokens": m.tokens,
                            "total_yes": total_yes,
                            "overprice": total_yes - 1.0,
                        },
                    ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        tokens = opportunity.metadata.get("tokens", [])
        overprice = opportunity.metadata.get("overprice", 0)

        if overprice < self.MIN_OVERPRICE:
            return None

        # Find most overpriced token to sell NO against
        most_overpriced = max(tokens, key=lambda t: float(t.get("price", 0)))
        token_id = most_overpriced.get("token_id", "")
        yes_price = float(most_overpriced.get("price", 0))

        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="sell",  # Sell YES (equivalent to buy NO)
            estimated_prob=yes_price - overprice / len(tokens),  # Fair value lower
            market_price=yes_price,
            confidence=0.9,
            strategy_name=self.name,
            metadata={"overprice": overprice, "total_yes": opportunity.market_price},
        )

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
