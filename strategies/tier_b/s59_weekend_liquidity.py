# strategies/tier_b/s59_weekend_liquidity.py
"""
S59: Weekend Liquidity Drop Exploitation

Weekend liquidity on Polymarket drops 60-80%, causing wider bid-ask
spreads. This strategy places limit orders during weekend hours to
capture spread-widening opportunities, getting better entry prices
than would be possible during high-liquidity weekday trading.
"""
from datetime import datetime
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class WeekendLiquidity(BaseStrategy):
    name = "s59_weekend_liquidity"
    tier = "B"
    strategy_id = 59
    required_data = []

    WEEKEND_SPREAD_MULTIPLIER = 2.0  # Spreads ~2x wider on weekends
    NORMAL_SPREAD = 0.02             # Typical weekday spread
    MIN_SPREAD_EDGE = 0.02           # Minimum extra spread to exploit
    MIN_CONFIDENCE = 0.50

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Scan all active markets on weekends for wider spread opportunities."""
        if not self._is_weekend():
            return []

        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            # Look for markets where weekend liquidity drop is most impactful
            # Lower-liquidity markets are more affected
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

    def _is_weekend(self) -> bool:
        """Check if current day is Saturday (5) or Sunday (6)."""
        return datetime.now().weekday() >= 5

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Place limit orders at better prices during weekend spread widening."""
        market_price = opportunity.market_price
        # Weekend spreads are wider; place a bid below current midpoint
        estimated_weekend_spread = self.NORMAL_SPREAD * self.WEEKEND_SPREAD_MULTIPLIER
        bid_discount = estimated_weekend_spread / 2
        if bid_discount < self.MIN_SPREAD_EDGE:
            return None

        bid_price = round(market_price - bid_discount, 2)
        if bid_price <= 0 or bid_price >= 1:
            return None

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=market_price,
            market_price=bid_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "midpoint": market_price,
                "bid_discount": bid_discount,
                "estimated_spread": estimated_weekend_spread,
                "liquidity": opportunity.metadata.get("liquidity", 0),
            },
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
