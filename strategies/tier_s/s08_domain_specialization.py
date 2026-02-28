from typing import List, Optional
from core.models import Market, Opportunity, Signal, Order
from core.base_strategy import BaseStrategy


class DomainSpecialization(BaseStrategy):
    name = "s08_domain_specialization"
    tier = "S"
    strategy_id = 8
    required_data = []

    DOMAINS = {
        "politics": ["election", "president", "senate", "congress", "vote", "governor", "mayor"],
        "sports": ["nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball", "baseball"],
        "crypto": ["bitcoin", "ethereum", "btc", "eth", "crypto", "defi", "token"],
        "weather": ["temperature", "weather", "rain", "snow", "degrees"],
        "ai": ["artificial intelligence", "openai", "gpt", "claude", "ai model"],
        "geopolitics": ["war", "invasion", "nato", "sanctions", "ceasefire", "treaty"],
    }

    def __init__(self, focus_domain: str = "crypto"):
        super().__init__()
        self.focus_domain = focus_domain
        self.domain_keywords = self.DOMAINS.get(focus_domain, [])

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            q = m.question.lower()
            if any(kw in q for kw in self.domain_keywords):
                yes_price = self._get_yes_price(m)
                if yes_price is not None and m.volume > 1000:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id, question=m.question,
                        market_price=yes_price, category=self.focus_domain,
                        metadata={"tokens": m.tokens}
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        # Domain expert makes independent probability estimate
        # Then compares to market price
        # Placeholder: requires domain-specific analysis
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id, side=signal.side,
            price=signal.market_price, size=size, strategy_name=self.name
        )
