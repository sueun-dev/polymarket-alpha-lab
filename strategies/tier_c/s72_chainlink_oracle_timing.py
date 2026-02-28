# strategies/tier_c/s72_chainlink_oracle_timing.py
"""
S72: Chainlink Oracle Update Timing

Exploit the timing of Chainlink oracle updates to trade markets that
resolve based on on-chain oracle data.  If the oracle updates on a
known cadence, position just before the update when the market price
hasn't yet incorporated the latest off-chain value.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

ORACLE_KEYWORDS = ["oracle", "chainlink", "price feed", "on-chain"]


class ChainlinkOracleTiming(BaseStrategy):
    name = "s72_chainlink_oracle_timing"
    tier = "C"
    strategy_id = 72
    required_data = ["chainlink_feeds"]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets resolved via oracle data."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            text = (m.question + " " + m.description).lower()
            if not any(kw in text for kw in ORACLE_KEYWORDS):
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
        """Placeholder: requires Chainlink feed integration.

        In production this would:
        1. Check when the next oracle heartbeat is expected
        2. Compare current off-chain value to on-chain value
        3. If divergence exists, trade ahead of the update
        """
        oracle_price = opportunity.metadata.get("oracle_price")
        if oracle_price is None:
            return None
        edge = oracle_price - opportunity.market_price
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
            estimated_prob=oracle_price,
            market_price=opportunity.market_price,
            confidence=0.40,
            strategy_name=self.name,
            metadata={"oracle_price": oracle_price},
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
