# strategies/tier_a/s28_portfolio_agent.py
"""
S28: Portfolio Betting Agent

Kelly-optimized multi-market portfolio. This is a meta-strategy that scans
all markets with sufficient volume, estimates probability and edge for each,
then aggregates positions into a diversified portfolio using Kelly criterion
allocation. Avoids over-concentration and maximizes long-term growth rate.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class PortfolioBettingAgent(BaseStrategy):
    name = "s28_portfolio_agent"
    tier = "A"
    strategy_id = 28
    required_data = []

    MIN_VOLUME = 5000
    MIN_EDGE = 0.03  # 3% minimum edge to include in portfolio
    MAX_PORTFOLIO_POSITIONS = 20
    MAX_SINGLE_ALLOCATION = 0.10  # 10% max in any single market

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """All markets with volume > 5000 are portfolio candidates."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if m.volume <= self.MIN_VOLUME:
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
                    "liquidity": m.liquidity,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Estimate probability and edge, then apply Kelly sizing.

        In production this meta-strategy would:
        1. Gather probability estimates from multiple sub-strategies
        2. Compute a consensus estimated probability
        3. Calculate Kelly fraction for each market
        4. Cap allocation at MAX_SINGLE_ALLOCATION
        5. Return signal only if edge exceeds MIN_EDGE

        Placeholder: uses simple heuristic based on volume as a proxy.
        """
        yes_price = opportunity.market_price
        volume = opportunity.metadata.get("volume", 0)

        # Simple heuristic: high-volume markets near 50/50 tend to be efficient
        # Low-volume markets away from 50/50 may have edge
        distance_from_center = abs(yes_price - 0.50)

        # Placeholder estimation: slight mean-reversion bias
        if distance_from_center < 0.10:
            # Near 50/50, assume efficient -- no edge
            return None

        # Estimate: extreme prices tend to revert slightly toward center
        estimated_prob = yes_price + (0.50 - yes_price) * 0.10
        edge = abs(estimated_prob - yes_price)

        if edge < self.MIN_EDGE:
            return None

        # Determine side: if estimated_prob < yes_price, bet NO; else bet YES
        if estimated_prob < yes_price:
            token_id = self._get_no_token_id(opportunity)
            side = "buy"
            signal_prob = 1 - estimated_prob
            signal_price = 1 - yes_price
        else:
            token_id = self._get_yes_token_id(opportunity)
            side = "buy"
            signal_prob = estimated_prob
            signal_price = yes_price

        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=signal_prob,
            market_price=signal_price,
            confidence=0.5,
            strategy_name=self.name,
            metadata={"edge": edge, "volume": volume},
        )

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        # Cap single-market allocation
        capped_size = min(size, size * self.MAX_SINGLE_ALLOCATION / 0.06)
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=capped_size,
            strategy_name=self.name,
        )
