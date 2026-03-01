# strategies/tier_s/s01_reversing_stupidity.py
"""
S01: Reversing Stupidity

Bet against emotionally overheated markets. After big events (elections,
major decisions), supporters flood markets with irrational bets.
Systematically take the opposite side.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ReversingStupidity(BaseStrategy):
    name = "s01_reversing_stupidity"
    tier = "S"
    strategy_id = 1
    required_data = ["base_rates", "news"]

    OVERREACTION_KEYWORDS = [
        "trump", "maga", "war", "crash", "moon",
        "100%", "guaranteed", "inevitable",
    ]
    OVERREACTION_THRESHOLD = 0.20  # 20% overpriced
    VOLUME_SPIKE_MULTIPLIER = 3.0

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with high volume AND question contains emotional keywords."""
        opportunities = []
        for m in markets:
            q_lower = m.question.lower()
            has_keyword = any(kw in q_lower for kw in self.OVERREACTION_KEYWORDS)
            if has_keyword and m.volume > 10000:
                # Get YES token price (first token)
                yes_price = self._get_yes_price(m)
                if yes_price and yes_price > 0.65:  # Likely overpriced YES
                    opportunities.append(Opportunity(
                        market_id=m.condition_id,
                        question=m.question,
                        market_price=yes_price,
                        category=m.category,
                        metadata={"tokens": m.tokens, "volume": m.volume},
                    ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        yes_price = opportunity.market_price

        # Use category-specific base rate if available
        base_rates = self.get_data("base_rates")
        news = self.get_data("news")

        if base_rates is not None:
            # Use category base rate for the "fair value" of dramatic events
            category = opportunity.category or "unknown"
            no_rate = base_rates.get_no_rate(category)
            base_rate = 1.0 - no_rate  # YES fair value
        else:
            base_rate = 0.50  # Original fallback

        # If news provider available, check for volume-driving sentiment
        if news is not None:
            sentiment_data = news.get_sentiment_for_market(opportunity.question)
            if sentiment_data and sentiment_data.get("avg_sentiment", 0) > 0.3:
                # Positive sentiment driving YES up -- even more likely overpriced
                base_rate *= 0.9  # Reduce fair value further

        if yes_price - base_rate < self.OVERREACTION_THRESHOLD:
            return None

        # Bet NO (sell YES equivalent)
        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",  # Buy NO
            estimated_prob=1 - base_rate,  # NO probability
            market_price=1 - yes_price,  # NO price
            confidence=0.7,
            strategy_name=self.name,
            metadata={"yes_price": yes_price, "base_rate": base_rate},
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
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=size,
            strategy_name=self.name,
        )
