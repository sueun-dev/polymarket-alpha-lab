# strategies/tier_c/s98_multi_timeframe.py
"""
S98: Multi-Timeframe Analysis

Compare short-, medium-, and long-term price trends for each market.
When all three timeframes align in one direction, the signal is
stronger.  Divergence across timeframes may indicate an impending
reversal.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MultiTimeframeAnalysis(BaseStrategy):
    name = "s98_multi_timeframe"
    tier = "C"
    strategy_id = 98
    required_data = []

    MIN_TREND_STRENGTH = 0.03  # Minimum trend magnitude to be meaningful

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Collect all active markets for multi-timeframe analysis."""
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
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Compare short/medium/long-term trends."""
        short = opportunity.metadata.get("trend_short")   # e.g. 1h
        medium = opportunity.metadata.get("trend_medium")  # e.g. 24h
        long = opportunity.metadata.get("trend_long")      # e.g. 7d
        if short is None or medium is None or long is None:
            return None

        # All three trends must agree and be strong enough
        all_positive = short > self.MIN_TREND_STRENGTH and medium > self.MIN_TREND_STRENGTH and long > self.MIN_TREND_STRENGTH
        all_negative = short < -self.MIN_TREND_STRENGTH and medium < -self.MIN_TREND_STRENGTH and long < -self.MIN_TREND_STRENGTH

        if not (all_positive or all_negative):
            return None

        avg_trend = (short + medium + long) / 3.0
        side = "buy" if avg_trend > 0 else "sell"
        estimated_prob = max(0.01, min(0.99, opportunity.market_price + avg_trend))

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.50,
            strategy_name=self.name,
            metadata={
                "trend_short": short,
                "trend_medium": medium,
                "trend_long": long,
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
