# strategies/tier_c/s73_chinese_archetype.py
"""
S73: Chinese "Three Trader Archetype" Classification

Classify on-chain traders into three archetypes from Chinese trading
philosophy: arbitrageur, speculator, or market-maker.  Use the
classification to predict order-flow impact and fade or follow
accordingly.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

ARCHETYPES = ["arbitrageur", "speculator", "market_maker"]


class ChineseArchetype(BaseStrategy):
    name = "s73_chinese_archetype"
    tier = "C"
    strategy_id = 73
    required_data = ["orderflow"]

    MIN_VOLUME = 1000

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Scan all active markets for archetype classification."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if m.volume < self.MIN_VOLUME:
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
        """Classify dominant trader archetype and trade accordingly.

        - arbitrageur-dominated: market is efficiently priced, skip
        - speculator-dominated: fade the speculative flow
        - market_maker-dominated: follow the market-maker's positioning
        """
        archetype = opportunity.metadata.get("dominant_archetype")
        if archetype not in ARCHETYPES:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        if archetype == "arbitrageur":
            return None  # efficiently priced
        elif archetype == "speculator":
            # Fade: if speculators are buying (price high), sell
            estimated = max(0.01, opportunity.market_price - 0.08)
            side = "sell"
        else:  # market_maker
            # Follow market-maker positioning
            estimated = min(0.99, opportunity.market_price + 0.06)
            side = "buy"

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated,
            market_price=opportunity.market_price,
            confidence=0.35,
            strategy_name=self.name,
            metadata={"dominant_archetype": archetype},
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
