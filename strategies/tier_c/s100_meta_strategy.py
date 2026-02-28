# strategies/tier_c/s100_meta_strategy.py
"""
S100: Meta-Strategy -- Weighted Ensemble

Combine signals from multiple other strategies into a single
weighted ensemble.  Each sub-strategy's signal is weighted by
its historical accuracy.  The meta-strategy only acts when the
ensemble confidence exceeds a threshold.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MetaStrategy(BaseStrategy):
    name = "s100_meta_strategy"
    tier = "C"
    strategy_id = 100
    required_data = []

    ENSEMBLE_THRESHOLD = 0.55  # Minimum weighted probability to act
    MIN_SUB_SIGNALS = 2  # Need at least 2 sub-strategy signals

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Collect all active markets for ensemble scoring."""
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
        """Weighted ensemble of other strategy signals."""
        sub_signals = opportunity.metadata.get("sub_signals", [])
        if len(sub_signals) < self.MIN_SUB_SIGNALS:
            return None

        # Each sub_signal: {"strategy": str, "prob": float, "weight": float}
        total_weight = sum(s.get("weight", 0) for s in sub_signals)
        if total_weight == 0:
            return None

        weighted_prob = sum(
            s.get("prob", 0) * s.get("weight", 0) for s in sub_signals
        ) / total_weight

        edge = weighted_prob - opportunity.market_price
        if abs(edge) < 0.03:
            return None

        side = "buy" if edge > 0 else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=weighted_prob,
            market_price=opportunity.market_price,
            confidence=min(0.80, total_weight / len(sub_signals)),
            strategy_name=self.name,
            metadata={
                "weighted_prob": weighted_prob,
                "num_signals": len(sub_signals),
                "total_weight": total_weight,
            },
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
