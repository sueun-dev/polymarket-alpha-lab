# strategies/tier_c/s97_smart_contract_event.py
"""
S97: Smart Contract Event Monitoring

Listen for on-chain events related to market resolution (e.g.
condition resolution callbacks, oracle price feeds).  The scan
step filters for markets that resolve on-chain; the analyze step
is a placeholder for real-time event processing.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class SmartContractEventMonitor(BaseStrategy):
    name = "s97_smart_contract_event"
    tier = "C"
    strategy_id = 97
    required_data = []

    ON_CHAIN_KEYWORDS = ["on-chain", "onchain", "smart contract", "oracle", "chainlink"]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with on-chain resolution mechanisms."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if not self._is_onchain_resolution(m):
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "onchain": True},
            ))
        return opportunities

    def _is_onchain_resolution(self, market: Market) -> bool:
        desc = market.description.lower()
        return any(kw in desc for kw in self.ON_CHAIN_KEYWORDS)

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: react to on-chain resolution events."""
        event_outcome = opportunity.metadata.get("event_outcome")
        if event_outcome is None:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        # event_outcome: 1.0 means YES resolves, 0.0 means NO
        estimated_prob = float(event_outcome)
        edge = abs(estimated_prob - opportunity.market_price)
        if edge < 0.05:
            return None

        side = "buy" if estimated_prob > opportunity.market_price else "sell"
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.70,
            strategy_name=self.name,
            metadata={"event_outcome": event_outcome},
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
