from typing import List, Optional
from core.models import Market, Opportunity, Signal, Order
from core.base_strategy import BaseStrategy


class YesBiasExploitation(BaseStrategy):
    name = "s10_yes_bias"
    tier = "S"
    strategy_id = 10
    required_data = []

    EXCITING_KEYWORDS = ["first", "ever", "historic", "record", "breakthrough", "revolutionary", "unprecedented"]
    BASE_NO_RATE = 0.70
    MIN_EDGE = 0.03
    LONGSHOT_THRESHOLD = 0.10  # Avoid YES below this

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            q = m.question.lower()
            is_exciting = any(kw in q for kw in self.EXCITING_KEYWORDS)
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            # Flag overpriced YES: exciting markets OR generally biased
            if (is_exciting and yes_price > 0.20) or (yes_price > 0.30 and m.volume > 5000):
                opportunities.append(Opportunity(
                    market_id=m.condition_id, question=m.question,
                    market_price=yes_price, category=m.category,
                    metadata={"tokens": m.tokens, "exciting": is_exciting}
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        yes_price = opportunity.market_price
        no_price = 1 - yes_price
        estimated_no_prob = self.BASE_NO_RATE
        if opportunity.metadata.get("exciting"):
            estimated_no_prob = 0.75  # Exciting markets are even more overpriced on YES
        edge = estimated_no_prob - no_price
        if edge < self.MIN_EDGE:
            return None
        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None
        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",
            estimated_prob=estimated_no_prob,
            market_price=no_price,
            confidence=0.6,
            strategy_name=self.name,
        )

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id, side=signal.side,
            price=signal.market_price, size=size, strategy_name=self.name
        )
