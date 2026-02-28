# strategies/tier_c/s81_holiday_effect.py
"""
S81: Holiday Trading Effects

Exploit reduced trading activity around major holidays.  Liquidity
drops, spreads widen, and prices can drift from fair value.  Place
limit orders during holiday periods to capture mean-reversion when
normal activity resumes.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

# Major US holidays (month, day) - simplified
HOLIDAYS = [
    (1, 1), (1, 20), (2, 17), (5, 26), (7, 4),
    (9, 1), (10, 13), (11, 11), (11, 27), (12, 25),
]
HOLIDAY_WINDOW_DAYS = 2


class HolidayEffect(BaseStrategy):
    name = "s81_holiday_effect"
    tier = "C"
    strategy_id = 81
    required_data = []

    DRIFT_THRESHOLD = 0.03  # min price drift to exploit

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find all active markets during holiday windows."""
        if not self._near_holiday():
            return []
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
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "liquidity": m.liquidity,
                },
            ))
        return opportunities

    def _near_holiday(self) -> bool:
        today = datetime.now().date()
        year = today.year
        for month, day in HOLIDAYS:
            try:
                holiday = datetime(year, month, day).date()
            except ValueError:
                continue
            if abs((today - holiday).days) <= HOLIDAY_WINDOW_DAYS:
                return True
        return False

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Exploit holiday drift with limit orders at fair value.

        In production this would:
        1. Compute fair value from pre-holiday price
        2. Place limit order at fair value if market has drifted
        3. Profit when activity resumes and price reverts
        """
        pre_holiday_price = opportunity.metadata.get("pre_holiday_price")
        if pre_holiday_price is None:
            return None
        drift = opportunity.market_price - pre_holiday_price
        if abs(drift) < self.DRIFT_THRESHOLD:
            return None
        # Fade the drift: if price drifted up, sell; if down, buy
        side = "sell" if drift > 0 else "buy"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=pre_holiday_price,
            market_price=opportunity.market_price,
            confidence=0.35,
            strategy_name=self.name,
            metadata={"pre_holiday_price": pre_holiday_price, "drift": drift},
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
