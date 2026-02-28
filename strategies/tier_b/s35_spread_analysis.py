# strategies/tier_b/s35_spread_analysis.py
"""
S35: Bid-Ask Spread Analysis

Analyze bid-ask spreads to find markets where the spread is wide enough
to capture edge. Buy at the bid, sell at the ask for spread capture.
Target markets with spread > 5%.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class SpreadAnalysis(BaseStrategy):
    name = "s35_spread_analysis"
    tier = "B"
    strategy_id = 35
    required_data = []

    MIN_SPREAD = 0.05  # 5% minimum spread

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find wide-spread markets (spread > 5%)."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            spread_info = self._get_spread(m)
            if spread_info is None:
                continue
            bid, ask, spread = spread_info
            if spread > self.MIN_SPREAD:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=(bid + ask) / 2.0,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "bid": bid,
                        "ask": ask,
                        "spread": spread,
                        "volume": m.volume,
                    },
                ))
        return opportunities

    def _get_spread(self, market: Market) -> Optional[tuple]:
        """Derive spread from YES/NO token prices. Spread = 1 - YES - NO."""
        yes_price = None
        no_price = None
        for t in market.tokens:
            outcome = t.get("outcome", "").lower()
            price = float(t.get("price", 0))
            if outcome == "yes":
                yes_price = price
            elif outcome == "no":
                no_price = price
        if yes_price is None or no_price is None:
            return None
        # bid = NO price complement, ask = YES price
        bid = 1.0 - no_price
        ask = yes_price
        spread = ask - bid
        if spread <= 0:
            return None
        return bid, ask, spread

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Buy at bid, target sell at ask for spread capture."""
        bid = opportunity.metadata.get("bid", 0)
        ask = opportunity.metadata.get("ask", 0)
        spread = opportunity.metadata.get("spread", 0)
        if spread < self.MIN_SPREAD:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        midpoint = (bid + ask) / 2.0
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=midpoint,
            market_price=bid,  # Buy at bid
            confidence=0.5,
            strategy_name=self.name,
            metadata={"bid": bid, "ask": ask, "spread": spread},
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
