# strategies/tier_c/s85_microcap_monopoly.py
"""
S85: Monopolise Micro-Cap Markets

Target markets with very low liquidity (< $200) where becoming the
sole liquidity provider gives pricing power.  Post tight two-sided
quotes and earn the spread with minimal competition.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MicrocapMonopoly(BaseStrategy):
    name = "s85_microcap_monopoly"
    tier = "C"
    strategy_id = 85
    required_data = []

    MAX_LIQUIDITY = 200.0  # Only target markets under $200 liquidity
    SPREAD = 0.08          # Post 8-cent wide spread
    MIN_CONFIDENCE = 0.40

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with liquidity below $200."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if m.liquidity >= self.MAX_LIQUIDITY:
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
                    "volume": m.volume,
                    "liquidity": m.liquidity,
                },
            ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Post two-sided quotes to monopolise the spread.

        Strategy: place a bid at (mid - spread/2) and an ask at
        (mid + spread/2), earning the spread as the sole LP.
        """
        mid = opportunity.market_price
        bid = round(mid - self.SPREAD / 2, 2)
        ask = round(mid + self.SPREAD / 2, 2)

        if bid <= 0.01 or ask >= 0.99:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",  # lead with the bid side
            estimated_prob=mid,
            market_price=bid,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "bid": bid,
                "ask": ask,
                "spread": self.SPREAD,
                "liquidity": opportunity.metadata.get("liquidity", 0),
            },
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
