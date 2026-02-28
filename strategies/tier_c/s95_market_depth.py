# strategies/tier_c/s95_market_depth.py
"""
S95: Market Depth Analysis

Analyse the order book (market depth) for each market.  Large
imbalances between bid and ask depth signal directional pressure
that has not yet moved the mid-price.  Trade in the direction of
the heavier side.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MarketDepthAnalysis(BaseStrategy):
    name = "s95_market_depth"
    tier = "C"
    strategy_id = 95
    required_data = []

    IMBALANCE_THRESHOLD = 0.30  # 30 % imbalance to trigger

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Collect all active markets for depth analysis."""
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
        """Order book imbalance signals."""
        bid_depth = opportunity.metadata.get("bid_depth")
        ask_depth = opportunity.metadata.get("ask_depth")
        if bid_depth is None or ask_depth is None:
            return None

        total = bid_depth + ask_depth
        if total == 0:
            return None

        imbalance = (bid_depth - ask_depth) / total
        if abs(imbalance) < self.IMBALANCE_THRESHOLD:
            return None

        # Positive imbalance = more bids = buying pressure -> buy
        side = "buy" if imbalance > 0 else "sell"
        adjustment = imbalance * 0.10  # Shift probability by up to 10%
        estimated_prob = max(0.01, min(0.99, opportunity.market_price + adjustment))

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.40,
            strategy_name=self.name,
            metadata={"imbalance": imbalance, "bid_depth": bid_depth, "ask_depth": ask_depth},
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
