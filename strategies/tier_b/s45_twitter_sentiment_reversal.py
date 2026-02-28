# strategies/tier_b/s45_twitter_sentiment_reversal.py
"""
S45: Twitter Sentiment Reversal (Fade the Crowd)

Fade Twitter sentiment. When Twitter/X consensus is overwhelmingly
bullish or bearish on a prediction market outcome, retail sentiment
tends to overshoot. This strategy monitors social-media sentiment
and bets against the crowd when conviction reaches extreme levels.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class TwitterSentimentReversal(BaseStrategy):
    name = "s45_twitter_sentiment_reversal"
    tier = "B"
    strategy_id = 45
    required_data = ["twitter_sentiment"]

    SENTIMENT_EXTREME = 0.80  # Trigger when >80 % of tweets agree
    FADE_BOOST = 0.10  # Estimated edge from fading crowd
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Return all active markets (sentiment filtering is done in analyze)."""
        opportunities = []
        for m in markets:
            if not m.active:
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
        """Placeholder -- requires Twitter/X sentiment data.

        In production this would:
        1. Query Twitter/X API for recent posts mentioning the market topic
        2. Run sentiment analysis (NLP) to classify bullish vs bearish
        3. If sentiment > SENTIMENT_EXTREME bullish, fade by buying NO
        4. If sentiment > SENTIMENT_EXTREME bearish, fade by buying YES
        5. Size inversely to market liquidity
        """
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
