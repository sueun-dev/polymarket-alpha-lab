# strategies/tier_a/s24_model_vs_market.py
"""
S24: Model vs Market Divergence

Compare predictions from quantitative models (538, Silver Bulletin, The
Economist, etc.) against Polymarket prices. When a reputable model assigns
a significantly different probability, trade in the direction of the model.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ModelVsMarket(BaseStrategy):
    name = "s24_model_vs_market"
    tier = "A"
    strategy_id = 24
    required_data = ["models"]

    POLITICAL_KEYWORDS = [
        "election", "president", "senator", "governor", "congress",
        "house", "senate", "vote", "ballot", "primary", "nominee",
        "democrat", "republican", "gop",
    ]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find political/election markets suitable for model comparison."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_political = any(kw in q_lower for kw in self.POLITICAL_KEYWORDS)
            if not is_political:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category or "politics",
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder -- would compare external model probabilities to market."""
        # In production: fetch 538/Silver Bulletin model probability for this
        # event, compute divergence from market price. If |model - market| >
        # threshold, generate a signal in the direction of the model.
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
