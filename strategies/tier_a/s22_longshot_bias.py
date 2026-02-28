# strategies/tier_a/s22_longshot_bias.py
"""
S22: Longshot Bias Exploitation

Bettors systematically overpay for low-probability outcomes (longshots).
Research shows 60%+ of longshot buyers lose. This strategy sells overpriced
longshot contracts by buying the NO side at $0.85-$0.95, collecting near-
certain payoffs as most of these contracts expire worthless.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class LongshotBias(BaseStrategy):
    name = "s22_longshot_bias"
    tier = "A"
    strategy_id = 22
    required_data = []

    YES_PRICE_MIN = 0.05  # Minimum YES price to qualify as longshot
    YES_PRICE_MAX = 0.15  # Maximum YES price to qualify as longshot
    NO_BUY_MIN = 0.85     # Corresponding NO price floor
    NO_BUY_MAX = 0.95     # Corresponding NO price ceiling
    ESTIMATED_NO_PROB = 0.93  # Historical base rate: longshots rarely hit
    MIN_CONFIDENCE = 0.65

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets where YES is priced $0.05-$0.15 (longshot territory)."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            if self.YES_PRICE_MIN <= yes_price <= self.YES_PRICE_MAX:
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
        """Buy NO at $0.85-$0.95 -- most longshots don't hit."""
        yes_price = opportunity.market_price
        no_price = 1 - yes_price

        if not (self.NO_BUY_MIN <= no_price <= self.NO_BUY_MAX):
            return None

        edge = self.ESTIMATED_NO_PROB - no_price
        if edge <= 0:
            return None

        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",
            estimated_prob=self.ESTIMATED_NO_PROB,
            market_price=no_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={"yes_price": yes_price, "edge": edge},
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
