# strategies/tier_a/s13_vitalik_anti_irrational.py
"""
S13: Vitalik Anti-Irrational

Bet against "insane" markets. Inspired by Vitalik Buterin's observation that
some Polymarket questions involve extreme/absurd scenarios that are dramatically
overpriced. If YES > 0.10 for a truly absurd outcome, buy NO.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class VitalikAntiIrrational(BaseStrategy):
    name = "s13_vitalik_anti_irrational"
    tier = "A"
    strategy_id = 13
    required_data = []

    # Keywords indicating extreme/absurd scenarios
    ABSURD_KEYWORDS = [
        "nobel", "destroy", "collapse", "alien", "zombie",
        "extinction", "apocalypse", "nuclear war", "asteroid",
        "end of the world", "martial law", "world war",
        "dictator", "abolish", "secede",
    ]
    # If YES > this for an absurd market, it is mispriced
    ABSURD_YES_THRESHOLD = 0.10
    # Maximum YES price to bet against (don't fight very high prices)
    MAX_YES_PRICE = 0.50
    # Estimated true probability for absurd events
    ABSURD_TRUE_PROB = 0.02  # 2% is generous for most absurd scenarios

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with extreme/absurd scenarios that may be overpriced."""
        opportunities = []
        for m in markets:
            q_lower = m.question.lower()
            matched_keywords = [kw for kw in self.ABSURD_KEYWORDS if kw in q_lower]
            if not matched_keywords:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            if yes_price > self.ABSURD_YES_THRESHOLD:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "matched_keywords": matched_keywords,
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
        """If YES > 0.10 for a truly absurd outcome, buy NO."""
        yes_price = opportunity.market_price

        if yes_price < self.ABSURD_YES_THRESHOLD:
            return None
        if yes_price > self.MAX_YES_PRICE:
            return None  # Too risky to fight very high prices

        # NO is underpriced: true NO prob ~ 0.98, market NO price = 1 - yes_price
        no_price = 1 - yes_price
        estimated_no_prob = 1 - self.ABSURD_TRUE_PROB

        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",
            estimated_prob=estimated_no_prob,
            market_price=no_price,
            confidence=0.80,
            strategy_name=self.name,
            metadata={
                "yes_price": yes_price,
                "absurd_true_prob": self.ABSURD_TRUE_PROB,
                "matched_keywords": opportunity.metadata.get("matched_keywords", []),
            },
        )

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
