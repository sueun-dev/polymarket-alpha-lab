# strategies/tier_b/s48_options_hedging.py
"""
S48: Options-Style Position Hedging

Apply options-style hedging to prediction-market positions. Since
Polymarket offers both YES and NO tokens for each market, one can
construct hedged positions analogous to options spreads. This strategy
calculates hedge ratios and generates offsetting trades to limit
downside exposure on existing positions.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class OptionsHedgingStrategy(BaseStrategy):
    name = "s48_options_hedging"
    tier = "B"
    strategy_id = 48
    required_data = []

    HEDGE_RATIO_THRESHOLD = 0.20  # Min imbalance between YES/NO to hedge
    CONFIDENCE = 0.60

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets that have both YES and NO tokens."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = None
            no_price = None
            for t in m.tokens:
                outcome = t.get("outcome", "").lower()
                if outcome == "yes":
                    yes_price = float(t.get("price", 0))
                elif outcome == "no":
                    no_price = float(t.get("price", 0))
            if yes_price is None or no_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": m.volume,
                },
            ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Calculate hedge ratios for YES/NO token pairs.

        If YES + NO < 1.0 significantly, there is a free-money arbitrage
        (buy both). If YES + NO > 1.0 significantly, there is an
        overpricing that can be exploited by selling both. We generate a
        signal for the side that is cheaper (the hedge leg).
        """
        yes_price = opportunity.metadata.get("yes_price", 0)
        no_price = opportunity.metadata.get("no_price", 0)
        tokens = opportunity.metadata.get("tokens", [])

        spread = yes_price + no_price  # Should be ~1.0 in efficient market
        imbalance = abs(spread - 1.0)

        if imbalance < self.HEDGE_RATIO_THRESHOLD:
            return None

        if spread < 1.0:
            # Under-priced pair -- buy the cheaper side
            if yes_price <= no_price:
                token_id = self._find_token(tokens, "yes")
                market_price = yes_price
            else:
                token_id = self._find_token(tokens, "no")
                market_price = no_price
            estimated_prob = market_price + imbalance
            side = "buy"
        else:
            # Over-priced pair -- sell the more expensive side
            if yes_price >= no_price:
                token_id = self._find_token(tokens, "yes")
                market_price = yes_price
            else:
                token_id = self._find_token(tokens, "no")
                market_price = no_price
            estimated_prob = market_price - imbalance
            side = "sell"

        if not token_id:
            return None

        estimated_prob = max(0.01, min(estimated_prob, 0.99))

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=market_price,
            confidence=self.CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "yes_price": yes_price,
                "no_price": no_price,
                "spread": round(spread, 4),
                "imbalance": round(imbalance, 4),
            },
        )

    @staticmethod
    def _find_token(tokens: list, outcome: str) -> Optional[str]:
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
