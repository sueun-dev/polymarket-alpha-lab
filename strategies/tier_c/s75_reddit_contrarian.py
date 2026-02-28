# strategies/tier_c/s75_reddit_contrarian.py
"""
S75: Reddit Contrarian Sentiment

Fade Reddit consensus.  When a prediction market is heavily discussed
on Reddit with strong one-directional sentiment, take the opposite
position.  Retail crowds on Reddit tend to overreact and herd.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order

REDDIT_KEYWORDS = ["reddit", "wsb", "r/", "subreddit", "upvote"]


class RedditContrarian(BaseStrategy):
    name = "s75_reddit_contrarian"
    tier = "C"
    strategy_id = 75
    required_data = ["reddit_api"]

    CONTRARIAN_THRESHOLD = 0.70  # fade when >70% of Reddit is one-sided
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets actively discussed on Reddit."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            text = (m.question + " " + m.description).lower()
            if not any(kw in text for kw in REDDIT_KEYWORDS):
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
        """Fade Reddit consensus when sentiment is extreme.

        In production this would:
        1. Scrape Reddit for mentions and sentiment
        2. Compute bullish ratio
        3. If ratio > threshold, take the opposite side
        """
        reddit_bullish_ratio = opportunity.metadata.get("reddit_bullish_ratio")
        if reddit_bullish_ratio is None:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        # Fade the crowd
        if reddit_bullish_ratio > self.CONTRARIAN_THRESHOLD:
            # Reddit is too bullish -> sell / estimate lower prob
            estimated = max(0.01, opportunity.market_price - 0.10)
            side = "sell"
        elif reddit_bullish_ratio < (1 - self.CONTRARIAN_THRESHOLD):
            # Reddit is too bearish -> buy / estimate higher prob
            estimated = min(0.99, opportunity.market_price + 0.10)
            side = "buy"
        else:
            return None

        edge = abs(estimated - opportunity.market_price)
        if edge < self.MIN_EDGE:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated,
            market_price=opportunity.market_price,
            confidence=0.35,
            strategy_name=self.name,
            metadata={"reddit_bullish_ratio": reddit_bullish_ratio},
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
