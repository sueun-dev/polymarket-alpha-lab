# strategies/tier_a/s17_whale_basket.py
"""
S17: Whale Basket Copy Trading

Track top wallet consensus. When 80%+ of tracked whale wallets agree
on a market direction, follow them. Large sophisticated traders often
have better information or models.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class WhaleBasketCopyTrading(BaseStrategy):
    name = "s17_whale_basket"
    tier = "A"
    strategy_id = 17
    required_data = ["onchain"]

    MIN_VOLUME = 10000
    WHALE_CONSENSUS_THRESHOLD = 0.80  # 80% agreement required

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """All markets with volume > 10000."""
        opportunities = []
        for m in markets:
            if m.volume > self.MIN_VOLUME and m.active:
                yes_price = self._get_yes_price(m)
                if yes_price is not None:
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
        # Placeholder: real implementation would query on-chain data
        # to check if 80%+ of tracked whale wallets agree on direction.
        # Steps:
        #   1. Fetch positions of tracked wallets for this market
        #   2. Calculate consensus direction (YES vs NO)
        #   3. If consensus >= WHALE_CONSENSUS_THRESHOLD, generate signal
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
