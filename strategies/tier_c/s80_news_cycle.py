# strategies/tier_c/s80_news_cycle.py
"""
S80: News Cycle Positioning

Position based on the stage of the news cycle.  Markets overreact at
the "breaking" stage and mean-revert during the "digest" stage.  Fade
the initial move, then follow if the story has legs during "follow-up".

Stages: breaking -> digest -> follow_up -> stale
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

NEWS_KEYWORDS = ["breaking", "news", "report", "announce", "update", "headline"]
VALID_STAGES = ["breaking", "digest", "follow_up", "stale"]


class NewsCyclePositioning(BaseStrategy):
    name = "s80_news_cycle"
    tier = "C"
    strategy_id = 80
    required_data = ["news_feed"]

    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets in active news cycles."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            text = (m.question + " " + m.description).lower()
            if not any(kw in text for kw in NEWS_KEYWORDS):
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
        """Position based on news cycle stage.

        - breaking: fade the initial spike (sell if price jumped)
        - digest: no action, wait for clarity
        - follow_up: follow if story has legs
        - stale: skip
        """
        stage = opportunity.metadata.get("news_stage")
        if stage not in VALID_STAGES:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        price = opportunity.market_price
        if stage == "breaking":
            # Fade the overreaction
            estimated = max(0.01, price - 0.10)
            side = "sell"
        elif stage == "follow_up":
            # Story has legs, follow the move
            estimated = min(0.99, price + 0.08)
            side = "buy"
        else:
            return None

        edge = abs(estimated - price)
        if edge < self.MIN_EDGE:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated,
            market_price=price,
            confidence=0.35,
            strategy_name=self.name,
            metadata={"news_stage": stage},
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
