# strategies/tier_a/s20_event_catalyst.py
"""
S20: Event Catalyst Pre-positioning

Position before known catalysts (FOMC, earnings, elections, verdicts).
Markets often misprice the impact of imminent known events. Find
markets with end dates 3-7 days away that reference catalyst keywords.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class EventCatalystPrePositioning(BaseStrategy):
    name = "s20_event_catalyst"
    tier = "A"
    strategy_id = 20
    required_data = []

    CATALYST_KEYWORDS = [
        "fed", "fomc", "earnings", "election",
        "trial", "verdict", "vote", "ruling",
        "announcement", "report", "decision",
    ]
    MIN_DAYS = 3
    MAX_DAYS = 7
    INEFFICIENCY_THRESHOLD = 0.15  # Price far from 0 or 1

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with end dates 3-7 days away."""
        opportunities = []
        now = datetime.now(tz=timezone.utc)

        for m in markets:
            if not m.active or not m.end_date_iso:
                continue

            try:
                end_date = datetime.fromisoformat(m.end_date_iso.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            days_until = (end_date - now).days
            if not (self.MIN_DAYS <= days_until <= self.MAX_DAYS):
                continue

            q_lower = m.question.lower()
            has_catalyst = any(kw in q_lower for kw in self.CATALYST_KEYWORDS)
            if not has_catalyst:
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
                    "end_date_iso": m.end_date_iso,
                    "days_until": days_until,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """If market appears inefficient before catalyst, signal."""
        yes_price = opportunity.market_price

        # Market is inefficient if price is in the uncertain zone
        # (not near 0 or 1), suggesting the catalyst hasn't been priced in
        distance_from_extreme = min(yes_price, 1 - yes_price)
        if distance_from_extreme < self.INEFFICIENCY_THRESHOLD:
            return None  # Already near-certain outcome, no edge

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        # With catalyst approaching, estimate a slight directional bias
        # toward resolution. Conservative estimate: midpoint drifts
        # toward nearest extreme by ~5 cents
        if yes_price >= 0.50:
            estimated_prob = min(yes_price + 0.05, 0.95)
            side = "buy"
            token_id = yes_token_id
            market_price = yes_price
        else:
            no_token_id = self._get_no_token_id(opportunity)
            if not no_token_id:
                return None
            estimated_prob = min((1 - yes_price) + 0.05, 0.95)
            side = "buy"
            token_id = no_token_id
            market_price = 1 - yes_price

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=market_price,
            confidence=0.5,
            strategy_name=self.name,
            metadata={
                "days_until": opportunity.metadata.get("days_until"),
                "catalyst_type": "pre_event",
            },
        )

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
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
