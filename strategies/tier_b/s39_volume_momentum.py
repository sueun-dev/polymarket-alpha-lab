# strategies/tier_b/s39_volume_momentum.py
"""
S39: Volume Momentum Trading

Trade in the direction of volume momentum. Find markets with
significant volume increase (3x+) and follow price direction
when momentum is strong.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class VolumeMomentum(BaseStrategy):
    name = "s39_volume_momentum"
    tier = "B"
    strategy_id = 39
    required_data = []

    VOLUME_SPIKE_MULTIPLIER = 3.0
    BASE_VOLUME = 5000  # Minimum baseline volume to consider

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with significant volume increase (3x+ baseline)."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if m.volume < self.BASE_VOLUME * self.VOLUME_SPIKE_MULTIPLIER:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Follow momentum: if price is moving away from 0.50, follow direction."""
        yes_price = opportunity.market_price
        volume = opportunity.metadata.get("volume", 0)
        if volume < self.BASE_VOLUME * self.VOLUME_SPIKE_MULTIPLIER:
            return None

        tokens = opportunity.metadata.get("tokens", [])

        # Momentum direction: if YES > 0.55, momentum is bullish -> buy YES
        # If YES < 0.45, momentum is bearish -> buy NO
        if yes_price > 0.55:
            token_id = self._get_token_id(tokens, "yes")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=min(yes_price + 0.05, 0.95),
                market_price=yes_price,
                confidence=0.55,
                strategy_name=self.name,
                metadata={"direction": "bullish", "volume": volume},
            )
        elif yes_price < 0.45:
            token_id = self._get_token_id(tokens, "no")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=min((1 - yes_price) + 0.05, 0.95),
                market_price=1 - yes_price,
                confidence=0.55,
                strategy_name=self.name,
                metadata={"direction": "bearish", "volume": volume},
            )

        return None  # Near 0.50 -- no clear momentum

    def _get_token_id(self, tokens: list, outcome: str) -> Optional[str]:
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
