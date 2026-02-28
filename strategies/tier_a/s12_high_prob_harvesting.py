# strategies/tier_a/s12_high_prob_harvesting.py
"""
S12: High Probability Harvesting

Buy near-certain contracts ($0.95-$0.99) and hold to settlement at $1.00.
These are markets where the outcome is virtually guaranteed but the contract
hasn't settled yet. Annualized returns of 10-161% depending on time to
resolution.
"""
from datetime import datetime, timezone
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class HighProbHarvesting(BaseStrategy):
    name = "s12_high_prob_harvesting"
    tier = "A"
    strategy_id = 12
    required_data = []

    MIN_YES_PRICE = 0.93  # Scan threshold
    BUY_MIN_PRICE = 0.95  # Only buy above this
    BUY_MAX_PRICE = 0.99  # Don't buy at 1.00 (no profit)
    MAX_DAYS_TO_RESOLUTION = 30  # Prefer near-term resolution

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with YES price > 0.93 that are near resolution."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            if yes_price > self.MIN_YES_PRICE:
                days_left = self._days_to_resolution(m.end_date_iso)
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "end_date_iso": m.end_date_iso,
                        "days_left": days_left,
                        "volume": m.volume,
                    },
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _days_to_resolution(self, end_date_iso: Optional[str]) -> Optional[float]:
        """Calculate days remaining until market resolution."""
        if not end_date_iso:
            return None
        try:
            end_dt = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = end_dt - now
            return max(0, delta.total_seconds() / 86400)
        except (ValueError, TypeError):
            return None

    def _annualized_yield(self, buy_price: float, days_left: float) -> float:
        """Calculate annualized yield from buying at buy_price and settling at 1.00."""
        if buy_price >= 1.0 or days_left <= 0:
            return 0.0
        profit_pct = (1.0 - buy_price) / buy_price
        annualized = profit_pct * (365.0 / days_left)
        return round(annualized, 4)

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """If resolution is near and price is in range, signal to buy YES."""
        yes_price = opportunity.market_price
        days_left = opportunity.metadata.get("days_left")

        # Must be within buy range
        if yes_price < self.BUY_MIN_PRICE or yes_price > self.BUY_MAX_PRICE:
            return None

        # Prefer markets with known, near-term resolution
        if days_left is not None and days_left > self.MAX_DAYS_TO_RESOLUTION:
            return None

        # Calculate annualized yield
        effective_days = days_left if days_left and days_left > 0 else 7  # default assumption
        annualized = self._annualized_yield(yes_price, effective_days)

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=0.99,  # We believe it will resolve YES
            market_price=yes_price,
            confidence=0.90,
            strategy_name=self.name,
            metadata={
                "days_left": days_left,
                "annualized_yield": annualized,
            },
        )

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
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
