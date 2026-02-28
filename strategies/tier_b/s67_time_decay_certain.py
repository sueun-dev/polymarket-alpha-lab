# strategies/tier_b/s67_time_decay_certain.py
"""
S67: Time Decay on Near-Certain Outcomes

Buy YES tokens priced > $0.90 on markets with short time to resolution.
As the event approaches and the outcome remains on track, the price
converges toward $1.00 -- effectively earning theta.  The edge comes
from harvesting the residual risk premium that the market demands on
near-certainties.
"""
from datetime import datetime, timezone
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class TimeDecayCertainOutcome(BaseStrategy):
    name = "s67_time_decay_certain"
    tier = "B"
    strategy_id = 67
    required_data = []

    MIN_YES_PRICE = 0.90
    MAX_DAYS_TO_EXPIRY = 14  # Only look at markets expiring within 2 weeks
    ESTIMATED_PROB = 0.96  # Assume near-certain events resolve YES ~96%
    MIN_EDGE = 0.03

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with YES > $0.90 and short time to resolution."""
        opportunities: List[Opportunity] = []
        now = datetime.now(timezone.utc)
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None or yes_price < self.MIN_YES_PRICE:
                continue
            days_left = self._days_to_expiry(m, now)
            if days_left is None or days_left > self.MAX_DAYS_TO_EXPIRY:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "days_left": days_left,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _days_to_expiry(self, market: Market, now: datetime) -> Optional[float]:
        if not market.end_date_iso:
            return None
        try:
            end = datetime.fromisoformat(market.end_date_iso.replace("Z", "+00:00"))
            delta = (end - now).total_seconds() / 86400.0
            return max(0.0, delta)
        except (ValueError, TypeError):
            return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Buy YES on near-certain outcomes, earning theta to expiry.

        In production this would:
        1. Verify the outcome is still on track (news, data feeds)
        2. Check there are no upcoming catalysts that could flip the result
        3. Compute time-adjusted probability (closer to 1.0 as expiry nears)
        4. Trade if the YES price is below our estimated probability
        """
        yes_price = opportunity.market_price
        days_left = opportunity.metadata.get("days_left", self.MAX_DAYS_TO_EXPIRY)

        # Closer to expiry -> higher confidence the outcome holds
        time_factor = max(0.0, 1.0 - days_left / self.MAX_DAYS_TO_EXPIRY)
        estimated_prob = self.ESTIMATED_PROB + time_factor * (1.0 - self.ESTIMATED_PROB) * 0.5
        estimated_prob = min(0.99, estimated_prob)

        edge = estimated_prob - yes_price
        if edge < self.MIN_EDGE:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=yes_price,
            confidence=0.65,
            strategy_name=self.name,
            metadata={"days_left": days_left, "theta_edge": edge},
        )

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
