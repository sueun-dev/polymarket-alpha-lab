# strategies/tier_b/s68_flash_crash_bot.py
"""
S68: Flash Crash Detection and Buying

Monitor for sudden, large price drops (20%+ within a short window)
that are likely due to thin-book liquidations rather than genuine
information.  Buy the dip and profit from the mean-reversion back to
fair value.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class FlashCrashBot(BaseStrategy):
    name = "s68_flash_crash_bot"
    tier = "B"
    strategy_id = 68
    required_data = ["price_history"]

    CRASH_THRESHOLD = 0.20  # 20% drop triggers detection
    MIN_PRIOR_PRICE = 0.30  # Ignore tokens already very cheap
    MIN_VOLUME = 5000  # Need meaningful volume to trade into
    RECOVERY_ESTIMATE = 0.70  # Expect 70% recovery of the drop

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Monitor for sudden 20%+ drops in YES token price."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if m.volume < self.MIN_VOLUME:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            # prior_price would be fetched from recent price history
            prior_price = self._get_prior_price(m)
            if prior_price is None or prior_price < self.MIN_PRIOR_PRICE:
                continue
            drop = (prior_price - yes_price) / prior_price
            if drop < self.CRASH_THRESHOLD:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "prior_price": prior_price,
                    "drop_pct": drop,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_prior_price(self, market: Market) -> Optional[float]:
        """Get the recent pre-crash price from token metadata.

        In production this would query a price-history service.
        """
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("prior_price")
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """If flash crash detected, estimate recovery price and buy.

        In production this would:
        1. Verify the drop is not information-driven (check news feeds)
        2. Check order-book depth on both sides
        3. Estimate recovery target based on historical mean-reversion
        4. Size position conservatively (flash crashes can continue)
        """
        prior_price = opportunity.metadata.get("prior_price")
        drop_pct = opportunity.metadata.get("drop_pct", 0.0)
        if prior_price is None or drop_pct < self.CRASH_THRESHOLD:
            return None

        current_price = opportunity.market_price
        recovery_target = current_price + (prior_price - current_price) * self.RECOVERY_ESTIMATE
        estimated_prob = min(0.99, recovery_target)

        edge = estimated_prob - current_price
        if edge < 0.05:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=current_price,
            confidence=0.50,
            strategy_name=self.name,
            metadata={
                "prior_price": prior_price,
                "drop_pct": drop_pct,
                "recovery_target": recovery_target,
            },
        )

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
