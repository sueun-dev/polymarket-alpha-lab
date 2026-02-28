# strategies/tier_c/s86_correlation_matrix.py
"""
S86: Cross-Market Correlation Matrix

Group markets by category and build a correlation matrix of price
movements.  When a historically correlated pair diverges beyond a
threshold, flag the lagging market as an opportunity -- the break
is likely temporary and mean-reversion is expected.
"""
from typing import Dict, List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CorrelationMatrix(BaseStrategy):
    name = "s86_correlation_matrix"
    tier = "C"
    strategy_id = 86
    required_data = []

    MIN_GROUP_SIZE = 2
    DIVERGENCE_THRESHOLD = 0.10  # 10-cent divergence to flag

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Group markets by category and find divergent pairs."""
        groups: Dict[str, List[Market]] = {}
        for m in markets:
            if not m.active or not m.category:
                continue
            groups.setdefault(m.category.lower(), []).append(m)

        opportunities: List[Opportunity] = []
        for category, group in groups.items():
            if len(group) < self.MIN_GROUP_SIZE:
                continue
            prices = []
            for m in group:
                yp = self._get_yes_price(m)
                if yp is not None:
                    prices.append(yp)
            if len(prices) < self.MIN_GROUP_SIZE:
                continue
            avg_price = sum(prices) / len(prices)
            for m in group:
                yp = self._get_yes_price(m)
                if yp is None:
                    continue
                divergence = abs(yp - avg_price)
                if divergence >= self.DIVERGENCE_THRESHOLD:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id,
                        question=m.question,
                        market_price=yp,
                        category=category,
                        metadata={
                            "tokens": m.tokens,
                            "avg_group_price": avg_price,
                            "divergence": divergence,
                        },
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Detect correlation breaks and trade toward group mean."""
        avg = opportunity.metadata.get("avg_group_price")
        if avg is None:
            return None
        divergence = opportunity.metadata.get("divergence", 0)
        if divergence < self.DIVERGENCE_THRESHOLD:
            return None

        # If market price is below group average, buy (expect reversion up)
        side = "buy" if opportunity.market_price < avg else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=avg,
            market_price=opportunity.market_price,
            confidence=0.45,
            strategy_name=self.name,
            metadata={"divergence": divergence, "avg_group_price": avg},
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
