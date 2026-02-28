# strategies/tier_a/s18_market_making.py
"""
S18: Automated Market Making

Provide two-sided liquidity in medium-liquidity markets. Calculate optimal
bid-ask spread around the midpoint and place orders on both sides.
Profit from the spread while providing liquidity.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class AutomatedMarketMaking(BaseStrategy):
    name = "s18_market_making"
    tier = "A"
    strategy_id = 18
    required_data = []

    MIN_LIQUIDITY = 1000
    MAX_LIQUIDITY = 100000
    DEFAULT_SPREAD = 0.04  # 4 cent spread (2 cents each side)
    MIN_PRICE = 0.10  # Avoid extremes
    MAX_PRICE = 0.90

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find medium-liquidity markets (not too high, not too low)."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if self.MIN_LIQUIDITY <= m.liquidity <= self.MAX_LIQUIDITY:
                yes_price = self._get_yes_price(m)
                if yes_price is not None and self.MIN_PRICE <= yes_price <= self.MAX_PRICE:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id,
                        question=m.question,
                        market_price=yes_price,
                        category=m.category,
                        metadata={
                            "tokens": m.tokens,
                            "liquidity": m.liquidity,
                        },
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Calculate optimal bid-ask spread around midpoint."""
        midpoint = opportunity.market_price
        half_spread = self.DEFAULT_SPREAD / 2

        bid_price = midpoint - half_spread
        ask_price = midpoint + half_spread

        # Ensure prices stay in valid range
        if bid_price < 0.01 or ask_price > 0.99:
            return None

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",  # Primary side is the bid
            estimated_prob=midpoint,
            market_price=midpoint,
            confidence=0.5,
            strategy_name=self.name,
            metadata={
                "bid_price": round(bid_price, 4),
                "ask_price": round(ask_price, 4),
                "spread": self.DEFAULT_SPREAD,
                "two_sided": True,
            },
        )

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        # Place the bid side order; in production would also place ask
        bid_price = signal.metadata.get("bid_price", signal.market_price)
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=bid_price,
            size=size,
            strategy_name=self.name,
        )
