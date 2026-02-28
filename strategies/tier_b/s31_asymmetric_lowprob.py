# strategies/tier_b/s31_asymmetric_lowprob.py
"""
S31: Asymmetric Low-Probability Bets

Bet on low-probability high-payout events. Find YES tokens priced
below $0.10 with meaningful volume, then evaluate whether the payoff
ratio justifies a small position.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class AsymmetricLowProb(BaseStrategy):
    name = "s31_asymmetric_lowprob"
    tier = "B"
    strategy_id = 31
    required_data = []

    MAX_YES_PRICE = 0.10  # Only look at YES tokens under $0.10
    MIN_VOLUME = 1000
    MIN_PAYOFF_RATIO = 10.0  # Require at least 10:1 payoff

    PLAUSIBILITY_KEYWORDS = [
        "will", "by", "before", "if", "could", "possible",
    ]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find YES tokens priced < $0.10 with volume > 1000."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            if yes_price < self.MAX_YES_PRICE and m.volume > self.MIN_VOLUME:
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

    def _is_plausible(self, question: str) -> bool:
        q = question.lower()
        return any(kw in q for kw in self.PLAUSIBILITY_KEYWORDS)

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        yes_price = opportunity.market_price
        if yes_price <= 0:
            return None

        payoff_ratio = (1.0 - yes_price) / yes_price
        if payoff_ratio < self.MIN_PAYOFF_RATIO:
            return None

        if not self._is_plausible(opportunity.question):
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=yes_price * 1.5,  # Slight edge assumption
            market_price=yes_price,
            confidence=0.4,
            strategy_name=self.name,
            metadata={"payoff_ratio": payoff_ratio},
        )

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
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
