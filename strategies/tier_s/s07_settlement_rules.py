from typing import List, Optional
from core.models import Market, Opportunity, Signal
from core.base_strategy import BaseStrategy


class SettlementRules(BaseStrategy):
    name = "s07_settlement_rules"
    tier = "S"
    strategy_id = 7
    required_data = []

    AMBIGUOUS_KEYWORDS = ["reserve", "official", "formal", "announce", "declare"]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            desc = m.description.lower()
            has_ambiguity = any(kw in desc for kw in self.AMBIGUOUS_KEYWORDS)
            if has_ambiguity and m.volume > 5000:
                yes_price = self._get_yes_price(m)
                if yes_price is not None:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id, question=m.question,
                        market_price=yes_price, category=m.category,
                        metadata={"tokens": m.tokens, "description": m.description}
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        # Real implementation: NLP analysis of resolution criteria vs headline
        # Placeholder logic: flag for manual review
        return None
