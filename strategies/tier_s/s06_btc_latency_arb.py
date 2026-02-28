from typing import List, Optional
from core.models import Market, Opportunity, Signal, Order
from core.base_strategy import BaseStrategy


class BTCLatencyArb(BaseStrategy):
    name = "s06_btc_latency_arb"
    tier = "S"
    strategy_id = 6
    required_data = ["cex_feed"]

    BTC_KEYWORDS = ["btc", "bitcoin", "15-minute", "15 minute", "hourly price"]
    PRICE_THRESHOLD = 0.005  # 0.5% price move = decisive

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            q = m.question.lower()
            is_btc = any(kw in q for kw in self.BTC_KEYWORDS)
            if is_btc and m.active:
                yes_price = self._get_yes_price(m)
                if yes_price is not None:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id, question=m.question,
                        market_price=yes_price, category="crypto",
                        metadata={"tokens": m.tokens}
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        # In production: compare CEX real-time price vs oracle price
        # If CEX confirms direction but market hasn't updated -> signal
        # Placeholder: return None (requires live CEX feed)
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id, side=signal.side,
            price=signal.market_price, size=size, strategy_name=self.name
        )
