# strategies/tier_b/s46_portfolio_rebalance.py
"""
S46: Periodic Portfolio Rebalancing

Rebalance a prediction-market portfolio toward target allocations.
When positions drift from their target weights (due to price moves),
this strategy generates signals to buy underweight positions and sell
overweight positions, maintaining diversification and risk control.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class PortfolioRebalanceStrategy(BaseStrategy):
    name = "s46_portfolio_rebalance"
    tier = "B"
    strategy_id = 46
    required_data = []

    DRIFT_THRESHOLD = 0.05  # Rebalance when weight drifts > 5 % from target
    CONFIDENCE = 0.60

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Return all active markets as candidates for portfolio inclusion."""
        opportunities = []
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
        """Rebalance toward target allocation.

        Expects metadata to contain:
        - 'target_weight': desired portfolio weight (e.g. 0.10 for 10 %)
        - 'current_weight': actual portfolio weight
        If current weight drifts from target by more than DRIFT_THRESHOLD,
        generate a buy (underweight) or sell (overweight) signal.
        """
        target = opportunity.metadata.get("target_weight")
        current = opportunity.metadata.get("current_weight")
        if target is None or current is None:
            return None

        drift = current - target
        if abs(drift) < self.DRIFT_THRESHOLD:
            return None

        tokens = opportunity.metadata.get("tokens", [])

        if drift < 0:
            # Underweight -> buy YES
            token_id = self._find_token(tokens, "yes")
            side = "buy"
        else:
            # Overweight -> sell YES
            token_id = self._find_token(tokens, "yes")
            side = "sell"

        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=opportunity.market_price,
            market_price=opportunity.market_price,
            confidence=self.CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "target_weight": target,
                "current_weight": current,
                "drift": round(drift, 4),
            },
        )

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
