# strategies/tier_c/s83_multilang_sentiment.py
"""
S83: Multi-Language Sentiment Analysis

Analyse sentiment across non-English sources (Mandarin, Spanish,
Arabic, etc.) for international markets.  English-language traders
may miss signals from foreign-language media and social platforms.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

INTERNATIONAL_KEYWORDS = [
    "china", "europe", "brazil", "india", "japan", "korea",
    "mexico", "germany", "france", "uk", "russia", "saudi",
    "international", "global", "world",
]


class MultilangSentiment(BaseStrategy):
    name = "s83_multilang_sentiment"
    tier = "C"
    strategy_id = 83
    required_data = ["translation_api"]

    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find international markets where foreign-language sentiment matters."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q = m.question.lower()
            if not any(kw in q for kw in INTERNATIONAL_KEYWORDS):
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: requires translation API.

        In production this would:
        1. Identify relevant languages for this market
        2. Scrape foreign-language news and social media
        3. Translate and run sentiment analysis
        4. Compare foreign vs English sentiment for edge
        """
        foreign_sentiment = opportunity.metadata.get("foreign_sentiment_score")
        if foreign_sentiment is None:
            return None
        edge = foreign_sentiment - opportunity.market_price
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
            estimated_prob=foreign_sentiment,
            market_price=opportunity.market_price,
            confidence=0.30,
            strategy_name=self.name,
            metadata={"foreign_sentiment_score": foreign_sentiment},
        )

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

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
