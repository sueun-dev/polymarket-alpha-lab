# strategies/tier_a/s15_news_mean_reversion.py
"""
S15: News Mean Reversion

Fade overreactions to news events. When a market price moves 15%+ in a short
period (24 hours) due to a news event, the initial reaction is often an
overreaction. Bet against the move, expecting mean reversion.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class NewsMeanReversion(BaseStrategy):
    name = "s15_news_mean_reversion"
    tier = "A"
    strategy_id = 15
    required_data = ["news"]

    PRICE_CHANGE_THRESHOLD = 0.15  # 15% price change triggers signal
    MEAN_REVERSION_FACTOR = 0.50  # Expect 50% reversion of the move
    MIN_VOLUME = 5000  # Minimum volume to ensure market is liquid

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with sudden price moves (15%+ in 24h)."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue

            # Check for price change data in token metadata
            price_change = self._get_price_change(m)
            if price_change is None:
                continue

            if abs(price_change) >= self.PRICE_CHANGE_THRESHOLD and m.volume >= self.MIN_VOLUME:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "price_change_24h": price_change,
                        "volume": m.volume,
                        "previous_price": yes_price - price_change,
                    },
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_price_change(self, market: Market) -> Optional[float]:
        """
        Extract 24h price change from token metadata.
        Looks for 'price_change_24h' field in YES token data.
        """
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                change = t.get("price_change_24h")
                if change is not None:
                    return float(change)
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """If price changed 15%+ in 24h, bet against the move."""
        price_change = opportunity.metadata.get("price_change_24h", 0)
        yes_price = opportunity.market_price
        previous_price = opportunity.metadata.get("previous_price", yes_price)

        if abs(price_change) < self.PRICE_CHANGE_THRESHOLD:
            return None

        # Expected reversion: price will move back toward previous level
        expected_reversion = price_change * self.MEAN_REVERSION_FACTOR
        fair_price = yes_price - expected_reversion

        tokens = opportunity.metadata.get("tokens", [])

        if price_change > 0:
            # Price spiked UP -- we think it will come back down, buy NO
            no_token_id = self._get_token_id(tokens, "no")
            if not no_token_id:
                return None
            estimated_no_prob = 1 - fair_price
            no_price = 1 - yes_price
            return Signal(
                market_id=opportunity.market_id,
                token_id=no_token_id,
                side="buy",
                estimated_prob=estimated_no_prob,
                market_price=no_price,
                confidence=0.60,
                strategy_name=self.name,
                metadata={
                    "price_change_24h": price_change,
                    "previous_price": previous_price,
                    "expected_reversion": expected_reversion,
                    "fair_yes_price": fair_price,
                },
            )
        else:
            # Price dropped DOWN -- we think it will bounce back, buy YES
            yes_token_id = self._get_token_id(tokens, "yes")
            if not yes_token_id:
                return None
            estimated_yes_prob = fair_price
            return Signal(
                market_id=opportunity.market_id,
                token_id=yes_token_id,
                side="buy",
                estimated_prob=estimated_yes_prob,
                market_price=yes_price,
                confidence=0.60,
                strategy_name=self.name,
                metadata={
                    "price_change_24h": price_change,
                    "previous_price": previous_price,
                    "expected_reversion": expected_reversion,
                    "fair_yes_price": fair_price,
                },
            )

    def _get_token_id(self, tokens: list, outcome: str) -> Optional[str]:
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
