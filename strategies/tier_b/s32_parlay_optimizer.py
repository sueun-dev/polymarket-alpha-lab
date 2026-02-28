# strategies/tier_b/s32_parlay_optimizer.py
"""
S32: Parlay Optimizer

Optimize multi-outcome parlay bets. Find multiple related NO markets
and check whether the combined NO probability exceeds the product of
individual NO probabilities -- if so, an arbitrage exists.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ParlayOptimizer(BaseStrategy):
    name = "s32_parlay_optimizer"
    tier = "B"
    strategy_id = 32
    required_data = []

    MIN_NO_PRICE = 0.50  # Only consider NO tokens priced above 50%

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find multiple related NO markets suitable for parlay analysis."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            no_price = self._get_no_price(m)
            if no_price is None:
                continue
            if no_price >= self.MIN_NO_PRICE:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=no_price,
                    category=m.category,
                    metadata={"tokens": m.tokens, "volume": m.volume},
                ))
        return opportunities

    def _get_no_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "no":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: would compare combined NO probability vs product of individual NOs."""
        # Real implementation would group related markets and compute parlay edges.
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
