# strategies/tier_b/s69_geopolitical_special.py
"""
S69: Geopolitical Event Specialization

Specialize in markets about geopolitical events: wars, peace treaties,
sanctions, territorial disputes, military exercises, and diplomatic
negotiations.  Geopolitical markets are noisy and emotionally driven;
regional expertise and pattern recognition can identify mispricings.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class GeopoliticalSpecialization(BaseStrategy):
    name = "s69_geopolitical_special"
    tier = "B"
    strategy_id = 69
    required_data = ["geopolitical"]

    GEO_KEYWORDS = [
        "war", "peace", "treaty", "sanction", "invasion",
        "ceasefire", "military", "nato", "un ", "united nations",
        "territorial", "conflict", "diplomat", "nuclear",
        "missile", "troops", "embargo", "annexation",
    ]
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets about geopolitical events."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_geo = any(kw in q_lower for kw in self.GEO_KEYWORDS)
            if not is_geo:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
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
        """Apply regional expertise to geopolitical markets.

        In production this would:
        1. Monitor diplomatic channels, satellite imagery feeds
        2. Track troop movements and military logistics data
        3. Analyse historical analogues (prior conflicts/negotiations)
        4. Score based on regional expertise model
        5. Trade if edge > MIN_EDGE
        """
        geo_score = opportunity.metadata.get("geo_score")
        if geo_score is None:
            return None

        estimated_prob = max(0.0, min(1.0, geo_score))
        edge = estimated_prob - opportunity.market_price

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
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.45,
            strategy_name=self.name,
            metadata={"geo_score": geo_score, "edge": edge},
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
