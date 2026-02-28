# strategies/tier_b/s42_insider_pattern.py
"""
S42: Insider-Like Pattern Detection

Detect insider-like trading patterns by monitoring for sudden large orders
that deviate significantly from normal volume. A spike in order size may
indicate informed trading. This strategy flags those markets and, with
sufficient order-flow data, would follow the informed direction.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class InsiderPatternDetection(BaseStrategy):
    name = "s42_insider_pattern"
    tier = "B"
    strategy_id = 42
    required_data = ["order_flow"]

    VOLUME_SPIKE_MULTIPLIER = 5.0  # Volume must be 5x the liquidity to flag
    MIN_VOLUME = 5000  # Minimum absolute volume to consider

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with sudden large orders (volume spike relative to liquidity)."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if m.volume < self.MIN_VOLUME:
                continue
            if m.liquidity <= 0:
                continue
            ratio = m.volume / m.liquidity
            if ratio < self.VOLUME_SPIKE_MULTIPLIER:
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
                    "volume_liquidity_ratio": round(ratio, 2),
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder -- requires order-flow data to determine informed direction.

        In production this would:
        1. Fetch recent order-flow / trade history for the market
        2. Identify abnormally large orders vs. trailing average
        3. Determine whether large orders are buying YES or NO
        4. Follow the informed direction if conviction is high
        """
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
