# strategies/tier_b/s50_multi_strategy_alloc.py
"""
S50: Multi-Strategy Capital Allocation

Meta-strategy that allocates capital across sub-strategies based on
their historical performance. It scans all markets, collects signals
from each registered sub-strategy, then weights position sizes by
each strategy's historical Sharpe ratio / win rate. Poorly-performing
strategies get reduced allocation; strong ones get increased allocation.
"""
from typing import Dict, List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MultiStrategyAllocation(BaseStrategy):
    name = "s50_multi_strategy_alloc"
    tier = "B"
    strategy_id = 50
    required_data = []

    DEFAULT_WEIGHT = 1.0 / 10  # Equal weight across 10 strategies initially
    MIN_WEIGHT = 0.02  # Floor at 2 % to avoid zero allocation
    MAX_WEIGHT = 0.30  # Cap at 30 % to avoid concentration
    CONFIDENCE = 0.60

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Return all active markets -- the meta-strategy considers everything."""
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
        """Allocate capital across strategies based on historical performance.

        Expects metadata to contain:
        - 'strategy_scores': dict mapping strategy_name -> performance score
        - 'best_strategy': name of the highest-scoring strategy for this market
        - 'best_signal': dict with the best strategy's signal details

        Without performance data, returns None (cold-start problem).
        """
        strategy_scores: Dict[str, float] = opportunity.metadata.get("strategy_scores", {})
        best_strategy = opportunity.metadata.get("best_strategy")
        best_signal = opportunity.metadata.get("best_signal")

        if not strategy_scores or not best_strategy or not best_signal:
            return None

        # Calculate weight for the best strategy
        total_score = sum(max(s, 0.01) for s in strategy_scores.values())
        if total_score <= 0:
            return None
        raw_weight = strategy_scores.get(best_strategy, 0) / total_score
        weight = max(self.MIN_WEIGHT, min(raw_weight, self.MAX_WEIGHT))

        token_id = best_signal.get("token_id", "")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=best_signal.get("side", "buy"),
            estimated_prob=best_signal.get("estimated_prob", opportunity.market_price),
            market_price=opportunity.market_price,
            confidence=self.CONFIDENCE * weight / self.DEFAULT_WEIGHT,
            strategy_name=self.name,
            metadata={
                "best_strategy": best_strategy,
                "allocated_weight": round(weight, 4),
                "strategy_scores": strategy_scores,
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
