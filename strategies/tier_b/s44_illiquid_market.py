# strategies/tier_b/s44_illiquid_market.py
"""
S44: Illiquid Market Inefficiency

Exploit illiquid market inefficiencies. Markets with low liquidity
(< $500) but meaningful volume (> $1000) often have wide bid-ask
spreads that create mispricing opportunities. This strategy identifies
those markets and looks for prices that deviate from fair value due
to thin order books.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class IlliquidMarketStrategy(BaseStrategy):
    name = "s44_illiquid_market"
    tier = "B"
    strategy_id = 44
    required_data = []

    MAX_LIQUIDITY = 500  # Markets must have liquidity below this
    MIN_VOLUME = 1000  # But volume must be above this (indicates interest)
    SPREAD_EDGE = 0.08  # Assumed edge from wide spreads
    MIN_EDGE = 0.05
    CONFIDENCE = 0.55

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with liquidity < 500 but volume > 1000."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if m.liquidity >= self.MAX_LIQUIDITY:
                continue
            if m.volume <= self.MIN_VOLUME:
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

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Wide spreads in illiquid markets create opportunity.

        If the market is illiquid and the YES price deviates substantially
        from 0.50 (center), assume the thin order book has pushed it away
        from fair value and trade toward center (mean reversion).
        """
        price = opportunity.market_price
        tokens = opportunity.metadata.get("tokens", [])

        # Distance from center -- illiquid markets tend to overshoot
        distance = abs(price - 0.50)
        if distance < self.MIN_EDGE:
            return None

        if price > 0.50:
            # Overpriced YES -> buy NO
            estimated_prob = (1.0 - price) + self.SPREAD_EDGE
            estimated_prob = min(estimated_prob, 0.99)
            token_id = self._find_token(tokens, "no")
            market_price = 1.0 - price
        else:
            # Underpriced YES -> buy YES
            estimated_prob = price + self.SPREAD_EDGE + distance
            estimated_prob = min(estimated_prob, 0.99)
            token_id = self._find_token(tokens, "yes")
            market_price = price

        if not token_id:
            return None

        edge = estimated_prob - market_price
        if edge < self.MIN_EDGE:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=market_price,
            confidence=self.CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "liquidity": opportunity.metadata.get("liquidity"),
                "volume": opportunity.metadata.get("volume"),
                "distance_from_center": round(distance, 4),
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
