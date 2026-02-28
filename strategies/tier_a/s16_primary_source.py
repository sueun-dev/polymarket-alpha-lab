# strategies/tier_a/s16_primary_source.py
"""
S16: Primary Source Monitoring

Monitor resolution sources directly (AP, government sites, court docs).
Markets that reference specific resolution sources are easier to predict
when you can monitor those sources before the crowd notices.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class PrimarySourceMonitoring(BaseStrategy):
    name = "s16_primary_source"
    tier = "A"
    strategy_id = 16
    required_data = ["news"]

    RESOLUTION_KEYWORDS = [
        "associated press", "ap news", "reuters",
        "government", "official", "court", "ruling",
        "sec filing", "fda", "department of",
        "bureau of", "census", "bls",
        "resolves according to", "resolution source",
    ]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with clear resolution sources mentioned in description."""
        opportunities = []
        for m in markets:
            desc_lower = m.description.lower()
            q_lower = m.question.lower()
            combined = desc_lower + " " + q_lower

            has_source = any(kw in combined for kw in self.RESOLUTION_KEYWORDS)
            if has_source and m.active:
                yes_price = self._get_yes_price(m)
                if yes_price is not None:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id,
                        question=m.question,
                        market_price=yes_price,
                        category=m.category,
                        metadata={
                            "tokens": m.tokens,
                            "description": m.description,
                            "volume": m.volume,
                        },
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        # Placeholder: real implementation would monitor RSS feeds,
        # government APIs, court docket systems, and news wires
        # to detect resolution-relevant events before the market reacts.
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
