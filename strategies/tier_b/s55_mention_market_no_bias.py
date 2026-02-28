# strategies/tier_b/s55_mention_market_no_bias.py
"""
S55: "Will X Mention Y" Markets - NO Bias

"Will X mention Y?" markets have a strong historical NO bias. Most
mention-type markets resolve NO because specific mentions are rare events.
This strategy systematically buys NO on mention markets, capturing the
base-rate edge that retail bettors ignore.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MentionMarketNoBias(BaseStrategy):
    name = "s55_mention_market_no_bias"
    tier = "B"
    strategy_id = 55
    required_data = []

    MENTION_KEYWORDS = ["mention", "say", "reference", "bring up", "talk about"]
    NO_BASE_RATE = 0.80         # Historical: ~80% of mention markets resolve NO
    MIN_EDGE = 0.04             # Minimum edge to act
    MIN_CONFIDENCE = 0.60

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with 'mention' or equivalent keywords."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            has_mention = any(kw in q_lower for kw in self.MENTION_KEYWORDS)
            if not has_mention:
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

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
                return t.get("token_id", "")
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Buy NO with base rate edge -- mention markets usually resolve NO."""
        yes_price = opportunity.market_price
        no_price = 1 - yes_price

        # Edge: our estimated NO probability vs current NO price
        edge = self.NO_BASE_RATE - no_price
        if edge < self.MIN_EDGE:
            return None

        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",
            estimated_prob=self.NO_BASE_RATE,
            market_price=no_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "yes_price": yes_price,
                "no_base_rate": self.NO_BASE_RATE,
                "edge": edge,
            },
        )

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
