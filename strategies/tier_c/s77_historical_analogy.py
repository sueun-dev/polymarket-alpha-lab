# strategies/tier_c/s77_historical_analogy.py
"""
S77: Historical Analogy Matching

Find similar historical events to establish base rates for current
political and economic prediction markets.  If a market asks about
a government shutdown, look at the historical frequency of shutdowns
under similar conditions.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

POLITICAL_ECON_KEYWORDS = [
    "election", "president", "senate", "congress", "shutdown",
    "recession", "gdp", "inflation", "fed", "rate", "tariff",
    "impeach", "veto", "treaty", "war", "ceasefire",
]


class HistoricalAnalogy(BaseStrategy):
    name = "s77_historical_analogy"
    tier = "C"
    strategy_id = 77
    required_data = []

    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find political/economic markets suitable for historical base-rate analysis."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q = m.question.lower()
            if not any(kw in q for kw in POLITICAL_ECON_KEYWORDS):
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
        """Estimate probability from historical base rate of analogous events.

        In production this would:
        1. Extract the event type from the question
        2. Query a historical-events database for analogues
        3. Compute base rate from matching events
        4. Adjust for current context differences
        """
        base_rate = opportunity.metadata.get("historical_base_rate")
        if base_rate is None:
            return None
        edge = base_rate - opportunity.market_price
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
            estimated_prob=base_rate,
            market_price=opportunity.market_price,
            confidence=0.40,
            strategy_name=self.name,
            metadata={"historical_base_rate": base_rate},
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
