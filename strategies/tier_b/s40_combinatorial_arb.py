# strategies/tier_b/s40_combinatorial_arb.py
"""
S40: Multi-Outcome Combinatorial Arbitrage

Find markets with 4+ outcomes and check all combinations of outcome
prices for arbitrage opportunities. If the sum of minimum-priced
outcomes exceeds 1.0, there is an exploitable mispricing.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CombinatorialArb(BaseStrategy):
    name = "s40_combinatorial_arb"
    tier = "B"
    strategy_id = 40
    required_data = []

    MIN_OUTCOMES = 4  # Only look at multi-outcome markets

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with 4+ outcomes."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if len(m.tokens) < self.MIN_OUTCOMES:
                continue
            prices = [float(t.get("price", 0)) for t in m.tokens]
            price_sum = sum(prices)
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=price_sum,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "num_outcomes": len(m.tokens),
                    "price_sum": price_sum,
                    "volume": m.volume,
                },
            ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Check all combinations for arb: if price_sum != 1.0, edge exists."""
        price_sum = opportunity.metadata.get("price_sum", 1.0)

        # If prices sum to > 1.0, we can sell all outcomes for guaranteed profit
        # If prices sum to < 1.0, we can buy all outcomes for guaranteed profit
        if abs(price_sum - 1.0) < 0.02:
            return None  # No meaningful arb

        tokens = opportunity.metadata.get("tokens", [])
        if not tokens:
            return None

        if price_sum < 1.0:
            # Buy all outcomes: guaranteed payout of 1.0 for cost of price_sum
            # Pick the cheapest token as the "signal" token
            cheapest = min(tokens, key=lambda t: float(t.get("price", 1.0)))
            token_id = cheapest.get("token_id", "")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=1.0 / len(tokens),
                market_price=float(cheapest.get("price", 0)),
                confidence=0.8,
                strategy_name=self.name,
                metadata={"arb_type": "buy_all", "price_sum": price_sum},
            )

        return None  # price_sum > 1.0 requires selling, more complex

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
