# strategies/tier_c/s89_gas_optimization.py
"""
S89: Polygon Gas Cost Optimization

Monitor Polygon network gas prices and time trade submissions to
periods of low gas, reducing transaction costs.  The scan step
collects all active markets; the analyze step evaluates whether
the current gas cost makes a trade worthwhile.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class GasOptimization(BaseStrategy):
    name = "s89_gas_optimization"
    tier = "C"
    strategy_id = 89
    required_data = []

    GAS_THRESHOLD_GWEI = 50  # Only trade when gas is below this

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Collect all active markets for gas-aware execution."""
        opportunities: List[Opportunity] = []
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
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Time trades for low gas periods on Polygon."""
        gas_price = opportunity.metadata.get("current_gas_gwei")
        if gas_price is None:
            return None
        if gas_price > self.GAS_THRESHOLD_GWEI:
            return None

        pending_signal = opportunity.metadata.get("pending_signal")
        if not pending_signal:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=pending_signal.get("side", "buy"),
            estimated_prob=pending_signal.get("estimated_prob", opportunity.market_price),
            market_price=opportunity.market_price,
            confidence=0.50,
            strategy_name=self.name,
            metadata={"gas_gwei": gas_price},
        )

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        for t in opportunity.metadata.get("tokens", []):
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
