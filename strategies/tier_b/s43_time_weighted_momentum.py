# strategies/tier_b/s43_time_weighted_momentum.py
"""
S43: Time-Weighted Momentum

Time-weighted momentum trading. If a market's price has been trending
in one direction over the past 7 days, follow the trend. This captures
persistent information flow that moves prices gradually rather than in
one jump. More recent price changes are weighted more heavily.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class TimeWeightedMomentumStrategy(BaseStrategy):
    name = "s43_time_weighted_momentum"
    tier = "B"
    strategy_id = 43
    required_data = []

    MOMENTUM_THRESHOLD = 0.05  # Minimum 5-cent move over 7 days to trigger
    TREND_BOOST = 0.10  # Estimated additional move in trend direction
    CONFIDENCE = 0.55
    MIN_EDGE = 0.03

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Return all active markets (momentum is evaluated in analyze)."""
        opportunities = []
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
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """If price trending in one direction over 7 days, follow trend.

        Expects opportunity.metadata to contain 'price_7d_ago'. Computes
        momentum = current_price - price_7d_ago. If momentum exceeds
        threshold, project further movement and generate a signal.
        """
        price_7d_ago = opportunity.metadata.get("price_7d_ago")
        if price_7d_ago is None:
            return None

        current_price = opportunity.market_price
        momentum = current_price - price_7d_ago

        if abs(momentum) < self.MOMENTUM_THRESHOLD:
            return None

        tokens = opportunity.metadata.get("tokens", [])

        if momentum > 0:
            # Upward trend -- buy YES
            estimated_prob = min(current_price + self.TREND_BOOST, 0.99)
            token_id = self._find_token(tokens, "yes")
            if not token_id:
                return None
            edge = estimated_prob - current_price
            if edge < self.MIN_EDGE:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=estimated_prob,
                market_price=current_price,
                confidence=self.CONFIDENCE,
                strategy_name=self.name,
                metadata={"momentum": round(momentum, 4), "direction": "up"},
            )
        else:
            # Downward trend -- buy NO
            estimated_prob = min((1.0 - current_price) + self.TREND_BOOST, 0.99)
            no_price = 1.0 - current_price
            token_id = self._find_token(tokens, "no")
            if not token_id:
                return None
            edge = estimated_prob - no_price
            if edge < self.MIN_EDGE:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=estimated_prob,
                market_price=no_price,
                confidence=self.CONFIDENCE,
                strategy_name=self.name,
                metadata={"momentum": round(momentum, 4), "direction": "down"},
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
