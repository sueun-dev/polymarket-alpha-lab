# strategies/tier_b/s41_resolution_timing.py
"""
S41: Resolution Timing

Trade markets approaching resolution. As markets near their end date
(within 48 hours), prices often drift toward extremes (0 or 1) as
uncertainty collapses. This strategy identifies near-resolution markets
where the price has not yet converged, and trades in the direction the
market is trending.
"""
from datetime import datetime, timezone
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ResolutionTimingStrategy(BaseStrategy):
    name = "s41_resolution_timing"
    tier = "B"
    strategy_id = 41
    required_data = []

    HOURS_THRESHOLD = 48  # Only consider markets ending within this window
    HIGH_PROB_THRESHOLD = 0.85  # Price above this -> likely YES resolution
    LOW_PROB_THRESHOLD = 0.15  # Price below this -> likely NO resolution
    CONFIDENCE = 0.70

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with end_date within 48 hours."""
        now = datetime.now(tz=timezone.utc)
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if not m.end_date_iso:
                continue
            try:
                end_dt = datetime.fromisoformat(m.end_date_iso.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            hours_remaining = (end_dt - now).total_seconds() / 3600
            if hours_remaining <= 0 or hours_remaining > self.HOURS_THRESHOLD:
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
                    "hours_remaining": round(hours_remaining, 2),
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Near-resolution markets often drift to extremes.

        If price > HIGH_PROB_THRESHOLD, bet YES (market resolving YES).
        If price < LOW_PROB_THRESHOLD, bet NO (market resolving NO).
        Otherwise, skip -- price is ambiguous.
        """
        price = opportunity.market_price
        tokens = opportunity.metadata.get("tokens", [])

        if price > self.HIGH_PROB_THRESHOLD:
            # Likely resolving YES -- buy YES
            token_id = self._find_token(tokens, "yes")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=0.95,
                market_price=price,
                confidence=self.CONFIDENCE,
                strategy_name=self.name,
                metadata={"hours_remaining": opportunity.metadata.get("hours_remaining")},
            )
        elif price < self.LOW_PROB_THRESHOLD:
            # Likely resolving NO -- buy NO
            token_id = self._find_token(tokens, "no")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=0.95,
                market_price=1.0 - price,
                confidence=self.CONFIDENCE,
                strategy_name=self.name,
                metadata={"hours_remaining": opportunity.metadata.get("hours_remaining")},
            )
        return None

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
