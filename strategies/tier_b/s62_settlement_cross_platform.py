# strategies/tier_b/s62_settlement_cross_platform.py
"""
S62: Cross-Platform Settlement Rule Arbitrage

Exploit differences in settlement rule interpretation across prediction
market platforms.  The same real-world question may resolve differently
on Polymarket vs Kalshi vs Metaculus due to differing fine-print.
When the settlement delta creates mispricing, arbitrage the gap.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class SettlementCrossPlatformArb(BaseStrategy):
    name = "s62_settlement_cross_platform"
    tier = "B"
    strategy_id = 62
    required_data = ["cross_platform"]

    PLATFORM_KEYWORDS = [
        "polymarket", "kalshi", "metaculus", "manifold",
        "predictit", "betfair", "smarkets",
    ]
    MIN_EDGE = 0.04

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets that exist on multiple platforms (via metadata)."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            # In production, cross-platform matching is done externally.
            # For scan, we surface every active market with a YES price so
            # the analyze step can check cross-platform data in metadata.
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            cross_platform_prices = m.description.lower()
            has_platform_ref = any(
                kw in cross_platform_prices for kw in self.PLATFORM_KEYWORDS
            )
            # Also accept markets explicitly tagged via metadata
            if not has_platform_ref and not m.category.lower().startswith("cross"):
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "description": m.description,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Compare settlement rules across platforms.

        In production this would:
        1. Match the market to equivalent markets on other platforms
        2. Parse settlement rules on each platform
        3. Identify where identical real-world outcome resolves differently
        4. Compute arb spread and trade if edge > MIN_EDGE
        """
        other_platform_price = opportunity.metadata.get("other_platform_price")
        if other_platform_price is None:
            return None

        edge = other_platform_price - opportunity.market_price
        if abs(edge) < self.MIN_EDGE:
            return None

        side = "buy" if edge > 0 else "sell"
        estimated_prob = other_platform_price

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.55,
            strategy_name=self.name,
            metadata={
                "other_platform_price": other_platform_price,
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
