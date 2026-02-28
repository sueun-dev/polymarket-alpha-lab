# strategies/tier_a/s19_kelly_framework.py
"""
S19: Kelly Sizing Framework

Meta-strategy wrapper that applies Kelly / Half-Kelly / Quarter-Kelly
position sizing to any signal from other strategies. Takes opportunities
with explicit probability estimates and computes optimal bet sizes.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.kelly import KellyCriterion
from core.models import Market, Opportunity, Signal, Order


class KellySizingFramework(BaseStrategy):
    name = "s19_kelly_framework"
    tier = "A"
    strategy_id = 19
    required_data = []

    # Kelly fractions
    FULL_KELLY = 1.0
    HALF_KELLY = 0.5
    QUARTER_KELLY = 0.25

    DEFAULT_FRACTION = QUARTER_KELLY  # Conservative default

    def __init__(self, kelly_fraction: float = None):
        super().__init__()
        fraction = kelly_fraction if kelly_fraction is not None else self.DEFAULT_FRACTION
        self.kelly = KellyCriterion(fraction=fraction)
        self.kelly_fraction = fraction

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Pass through all active markets."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is not None:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={"tokens": m.tokens},
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Apply Kelly criterion to opportunities with explicit probability estimates."""
        estimated_prob = opportunity.metadata.get("estimated_prob")
        if estimated_prob is None:
            return None

        market_price = opportunity.market_price
        if estimated_prob <= market_price:
            return None  # No edge

        kelly_fraction = self.kelly.optimal_size(
            p=estimated_prob,
            market_price=market_price,
        )
        if kelly_fraction <= 0:
            return None

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=market_price,
            confidence=min(estimated_prob - market_price, 1.0),
            strategy_name=self.name,
            metadata={
                "kelly_fraction": round(kelly_fraction, 6),
                "kelly_mode": self._kelly_mode_label(),
            },
        )

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def _kelly_mode_label(self) -> str:
        if self.kelly_fraction >= self.FULL_KELLY:
            return "full"
        elif self.kelly_fraction >= self.HALF_KELLY:
            return "half"
        else:
            return "quarter"

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
