from typing import List, Optional
from core.models import Market, Opportunity, Signal, Order
from core.base_strategy import BaseStrategy


class OracleLatency(BaseStrategy):
    name = "s09_oracle_latency"
    tier = "S"
    strategy_id = 9
    required_data = ["cex_feed"]

    HOURLY_KEYWORDS = ["hourly", "1-hour", "next hour", "by the hour"]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            q = m.question.lower()
            is_hourly = any(kw in q for kw in self.HOURLY_KEYWORDS)
            if is_hourly and m.active:
                yes_price = self._get_yes_price(m)
                if yes_price is not None:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id, question=m.question,
                        market_price=yes_price, category="oracle_latency",
                        metadata={"tokens": m.tokens}
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        # In production: compare real-time CEX price vs oracle update timing
        # If outcome already determined by CEX but oracle hasn't updated -> bet
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id, side=signal.side,
            price=signal.market_price, size=size, strategy_name=self.name
        )
