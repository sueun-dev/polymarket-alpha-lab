# strategies/tier_c/s84_token_merger_arb.py
"""
S84: Token Merger Arbitrage

Watch for markets that may merge or split their token structure.
When Polymarket restructures related markets (e.g. combining "Will X
win primary?" and "Will X win general?" into one), price dislocations
can occur.  Trade the dislocation before it corrects.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

MERGER_KEYWORDS = ["merge", "split", "restructur", "combin", "consolidat"]


class TokenMergerArb(BaseStrategy):
    name = "s84_token_merger_arb"
    tier = "C"
    strategy_id = 84
    required_data = []

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets that might undergo merge/split events."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            text = (m.question + " " + m.description).lower()
            if not any(kw in text for kw in MERGER_KEYWORDS):
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

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: requires monitoring of market structure changes.

        In production this would:
        1. Detect upcoming market restructuring events
        2. Calculate fair value of tokens post-merger/split
        3. Trade the dislocation between current and post-restructure price
        """
        post_restructure_price = opportunity.metadata.get("post_restructure_price")
        if post_restructure_price is None:
            return None
        edge = post_restructure_price - opportunity.market_price
        if abs(edge) < 0.05:
            return None
        side = "buy" if edge > 0 else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=post_restructure_price,
            market_price=opportunity.market_price,
            confidence=0.30,
            strategy_name=self.name,
            metadata={"post_restructure_price": post_restructure_price},
        )

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

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
