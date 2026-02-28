# strategies/tier_c/s74_bot_psychology.py
"""
S74: Bot Behaviour Reverse-Engineering

Identify automated trading bots by their low-latency, regular-interval
patterns and reverse-engineer their strategy to trade against or
alongside them.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class BotPsychology(BaseStrategy):
    name = "s74_bot_psychology"
    tier = "C"
    strategy_id = 74
    required_data = ["trade_history"]

    LOW_LATENCY_MS = 500  # trades under 500ms apart suggest bots
    MIN_BOT_TRADES = 10   # need enough trades to detect a pattern

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with very low-latency trading patterns."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            bot_trade_count = self._count_bot_trades(m)
            if bot_trade_count < self.MIN_BOT_TRADES:
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
                    "bot_trade_count": bot_trade_count,
                },
            ))
        return opportunities

    def _count_bot_trades(self, market: Market) -> int:
        """Count trades with latency below threshold.

        In production this would query trade-history for inter-trade
        intervals.  Here we read from token metadata as a placeholder.
        """
        for t in market.tokens:
            count = t.get("bot_trade_count")
            if count is not None:
                return int(count)
        return 0

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: requires trade-history analysis.

        In production this would:
        1. Cluster trades by timing fingerprint
        2. Classify bot strategy (MM, arb, trend-following)
        3. Predict next bot action and position accordingly
        """
        bot_bias = opportunity.metadata.get("bot_bias")
        if bot_bias is None:
            return None
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None
        estimated = min(0.99, max(0.01, opportunity.market_price + bot_bias))
        side = "buy" if bot_bias > 0 else "sell"
        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated,
            market_price=opportunity.market_price,
            confidence=0.30,
            strategy_name=self.name,
            metadata={"bot_bias": bot_bias},
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
