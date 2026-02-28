# strategies/tier_a/s29_earnings_streak.py
"""
S29: Earnings Beat Streak

Companies that consistently beat earnings estimates are underpriced on
prediction markets. If a company has 10+ consecutive earnings beats, the
market tends to anchor on base rates and underprice the next beat. This
strategy identifies earnings markets for serial beaters and bets YES.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class EarningsBeatStreak(BaseStrategy):
    name = "s29_earnings_streak"
    tier = "A"
    strategy_id = 29
    required_data = []

    EARNINGS_KEYWORDS = [
        "earnings", "revenue", "beat", "miss",
        "quarter", "q1", "q2", "q3", "q4",
    ]
    MIN_STREAK = 10  # Consecutive beats to trigger
    STREAK_PROB_BOOST = 0.75  # Estimated probability for serial beaters
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find earnings-related markets by keyword matching."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_earnings = any(kw in q_lower for kw in self.EARNINGS_KEYWORDS)
            if not is_earnings:
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
        """If company has 10+ consecutive beats, YES is likely underpriced.

        In production this would:
        1. Extract company name/ticker from the market question
        2. Look up historical earnings data (consecutive beat count)
        3. If streak >= MIN_STREAK, estimate higher probability of next beat
        4. Compare to market price and trade if edge exists
        """
        streak_count = opportunity.metadata.get("streak_count", 0)
        if streak_count < self.MIN_STREAK:
            return None

        yes_price = opportunity.market_price
        estimated_prob = self.STREAK_PROB_BOOST
        edge = estimated_prob - yes_price

        if edge < self.MIN_EDGE:
            return None

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=yes_price,
            confidence=0.65,
            strategy_name=self.name,
            metadata={"streak_count": streak_count, "edge": edge},
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
