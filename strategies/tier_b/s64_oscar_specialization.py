# strategies/tier_b/s64_oscar_specialization.py
"""
S64: Oscar / Awards Show Specialization

Specialize in entertainment awards markets (Oscars, Emmys, Grammys,
Golden Globes, etc.).  Awards markets tend to be dominated by casual
bettors who anchor on popularity rather than precursor signals (guild
awards, critics' picks, campaign spending).  This strategy applies
domain expertise to exploit that bias.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class OscarAwardsSpecialization(BaseStrategy):
    name = "s64_oscar_specialization"
    tier = "B"
    strategy_id = 64
    required_data = ["awards"]

    AWARD_KEYWORDS = [
        "oscar", "emmy", "grammy", "golden globe", "award",
        "best picture", "best actor", "best actress", "best director",
        "best film", "nomination", "bafta", "sag award", "tony",
    ]
    MIN_EDGE = 0.05
    PRECURSOR_PROB_BOOST = 0.12  # Boost if precursor signals align

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with awards-related keywords."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_award = any(kw in q_lower for kw in self.AWARD_KEYWORDS)
            if not is_award:
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
        """Apply awards-specific precursor analysis.

        In production this would:
        1. Check precursor awards (guilds, critics' circles)
        2. Analyse campaign spending and media buzz
        3. Review historical hit rate of precursor -> final winner
        4. Combine into estimated probability; trade if edge > MIN_EDGE
        """
        precursor_wins = opportunity.metadata.get("precursor_wins", 0)
        total_precursors = opportunity.metadata.get("total_precursors", 0)
        if total_precursors == 0:
            return None

        precursor_rate = precursor_wins / total_precursors
        estimated_prob = min(1.0, opportunity.market_price + precursor_rate * self.PRECURSOR_PROB_BOOST)
        edge = estimated_prob - opportunity.market_price

        if edge < self.MIN_EDGE:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.55,
            strategy_name=self.name,
            metadata={
                "precursor_wins": precursor_wins,
                "total_precursors": total_precursors,
                "precursor_rate": precursor_rate,
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
