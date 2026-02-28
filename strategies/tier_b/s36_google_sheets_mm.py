# strategies/tier_b/s36_google_sheets_mm.py
"""
S36: Google Sheets-Style Market Making

Simple market-making strategy inspired by spreadsheet-based approaches.
Scan for medium-volume markets and place orders at midpoint +/- spread.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class GoogleSheetsMM(BaseStrategy):
    name = "s36_google_sheets_mm"
    tier = "B"
    strategy_id = 36
    required_data = []

    MIN_VOLUME = 1000
    MAX_VOLUME = 50000  # Medium volume range
    HALF_SPREAD = 0.03  # Place orders 3% from midpoint

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find medium-volume markets suitable for market making."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            if not (self.MIN_VOLUME < m.volume < self.MAX_VOLUME):
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
        """Place orders at midpoint +/- spread."""
        midpoint = opportunity.market_price
        buy_price = midpoint - self.HALF_SPREAD
        if buy_price <= 0.01:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=midpoint,
            market_price=buy_price,
            confidence=0.5,
            strategy_name=self.name,
            metadata={
                "midpoint": midpoint,
                "buy_price": buy_price,
                "sell_price": midpoint + self.HALF_SPREAD,
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
