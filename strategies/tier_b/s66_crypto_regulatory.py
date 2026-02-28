# strategies/tier_b/s66_crypto_regulatory.py
"""
S66: Crypto Regulatory Outcome Specialization

Specialize in markets about crypto regulation (SEC enforcement, CFTC
jurisdiction, stablecoin bills, ETF approvals, etc.).  Regulatory
outcomes are path-dependent and follow patterns that domain specialists
can predict better than the general market.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CryptoRegulatorySpecialization(BaseStrategy):
    name = "s66_crypto_regulatory"
    tier = "B"
    strategy_id = 66
    required_data = ["regulatory"]

    REGULATORY_KEYWORDS = [
        "sec", "cftc", "regulation", "regulatory", "crypto",
        "bitcoin etf", "ethereum etf", "stablecoin", "enforcement",
        "lawsuit", "approve", "approval", "ban", "legal",
        "gensler", "congress", "bill", "act",
    ]
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find crypto regulation markets by keyword matching."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_reg = any(kw in q_lower for kw in self.REGULATORY_KEYWORDS)
            if not is_reg:
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
        """Analyze regulatory patterns and precedents.

        In production this would:
        1. Review SEC/CFTC filing history and enforcement cadence
        2. Parse congressional calendar and bill progress
        3. Assess political sentiment (committee hearings, lobbying data)
        4. Check judicial precedent for relevant cases
        5. Estimate probability from regulatory pattern model
        """
        regulatory_score = opportunity.metadata.get("regulatory_score")
        if regulatory_score is None:
            return None

        estimated_prob = max(0.0, min(1.0, regulatory_score))
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
            confidence=0.50,
            strategy_name=self.name,
            metadata={"regulatory_score": regulatory_score, "edge": edge},
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
