from typing import List, Optional
from core.models import Market, Opportunity, Signal, Order
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

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id, side=signal.side,
            price=signal.market_price, size=size, strategy_name=self.name
        )
