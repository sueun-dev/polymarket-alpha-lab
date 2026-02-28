# strategies/tier_c/s90_market_creation.py
"""
S90: New Market Creation Alpha

Newly created markets (< 24 hours old) often have thin liquidity and
mis-priced YES tokens.  This strategy scans for young markets and
attempts to identify early mispricing before informed traders arrive.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MarketCreationAlpha(BaseStrategy):
    name = "s90_market_creation"
    tier = "C"
    strategy_id = 90
    required_data = []

    MAX_AGE_HOURS = 24
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find newly created markets (< 24h old)."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            age_hours = self._market_age_hours(m)
            if age_hours is None or age_hours > self.MAX_AGE_HOURS:
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
                    "age_hours": age_hours,
                },
            ))
        return opportunities

    @staticmethod
    def _market_age_hours(market: Market) -> Optional[float]:
        """Return market age in hours from metadata, if available."""
        # In production this would compute from creation timestamp
        for t in market.tokens:
            age = t.get("age_hours")
            if age is not None:
                return float(age)
        return None

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Detect early mispricing in new markets."""
        fair_estimate = opportunity.metadata.get("fair_estimate")
        if fair_estimate is None:
            return None

        edge = fair_estimate - opportunity.market_price
        if abs(edge) < self.MIN_EDGE:
            return None

        side = "buy" if edge > 0 else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=fair_estimate,
            market_price=opportunity.market_price,
            confidence=0.40,
            strategy_name=self.name,
            metadata={
                "age_hours": opportunity.metadata.get("age_hours"),
                "edge": edge,
            },
        )

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        for t in opportunity.metadata.get("tokens", []):
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
