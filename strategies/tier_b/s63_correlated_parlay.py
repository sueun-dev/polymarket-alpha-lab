# strategies/tier_b/s63_correlated_parlay.py
"""
S63: Correlated Parlay Mispricing

When related markets in the same category are correlated, naive parlay
pricing (which assumes independence) will misprice the combined bet.
This strategy identifies correlated market clusters and exploits the
gap between independent-assumption parlay odds and true joint odds.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CorrelatedParlayMispricing(BaseStrategy):
    name = "s63_correlated_parlay"
    tier = "B"
    strategy_id = 63
    required_data = []

    MIN_EDGE = 0.04
    MIN_CORRELATION = 0.30  # Minimum absolute correlation to consider

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find related markets in the same category for parlay analysis."""
        # Group markets by category
        category_groups: dict[str, list[Market]] = {}
        for m in markets:
            if not m.active:
                continue
            cat = m.category.lower().strip()
            if not cat:
                continue
            category_groups.setdefault(cat, []).append(m)

        opportunities: List[Opportunity] = []
        for cat, group in category_groups.items():
            if len(group) < 2:
                continue
            for m in group:
                yes_price = self._get_yes_price(m)
                if yes_price is None:
                    continue
                # Attach sibling market IDs so analyze can compute correlations
                sibling_ids = [
                    s.condition_id for s in group if s.condition_id != m.condition_id
                ]
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=cat,
                    metadata={
                        "tokens": m.tokens,
                        "volume": m.volume,
                        "sibling_ids": sibling_ids,
                    },
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Check if parlay odds are mispriced due to ignored correlation.

        In production this would:
        1. Fetch price history for each sibling market
        2. Compute pairwise return correlations
        3. Price the parlay using copula / joint distribution
        4. Compare to the naive independent-assumption price
        5. Trade if mispricing > MIN_EDGE
        """
        correlation = opportunity.metadata.get("correlation")
        parlay_market_price = opportunity.metadata.get("parlay_market_price")
        if correlation is None or parlay_market_price is None:
            return None

        if abs(correlation) < self.MIN_CORRELATION:
            return None

        # Compute fair parlay price with correlation adjustment
        independent_price = opportunity.market_price  # Naive price
        corr_adjustment = correlation * 0.10  # Simplified adjustment
        fair_parlay_price = independent_price + corr_adjustment

        edge = fair_parlay_price - parlay_market_price
        if abs(edge) < self.MIN_EDGE:
            return None

        side = "buy" if edge > 0 else "sell"

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=fair_parlay_price,
            market_price=parlay_market_price,
            confidence=0.45,
            strategy_name=self.name,
            metadata={
                "correlation": correlation,
                "fair_parlay_price": fair_parlay_price,
                "edge": edge,
            },
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
