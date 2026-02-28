# strategies/tier_b/s49_stablecoin_yield.py
"""
S49: Stablecoin Yield Comparison

Compare prediction-market yield to stablecoin yield. High-probability
markets (e.g. 95 % chance of YES) offer an annualized return that may
exceed stablecoin lending rates. If the annualized return from buying
the high-prob token exceeds the stablecoin benchmark, this strategy
treats it as a superior yield opportunity and buys.
"""
from datetime import datetime, timezone
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class StablecoinYieldStrategy(BaseStrategy):
    name = "s49_stablecoin_yield"
    tier = "B"
    strategy_id = 49
    required_data = []

    HIGH_PROB_THRESHOLD = 0.90  # Only consider markets priced above this
    STABLECOIN_APY = 0.05  # 5 % baseline stablecoin yield to beat
    MIN_ANNUALIZED_EDGE = 0.02  # At least 2 % annualized above stablecoin
    CONFIDENCE = 0.75

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find high-probability markets that act as yield opportunities."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            if yes_price < self.HIGH_PROB_THRESHOLD:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "end_date_iso": m.end_date_iso,
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
        """If annualized return > stablecoin yield, buy the high-prob token.

        Annualized return = (1 / price - 1) * (365 / days_to_resolution).
        If this exceeds STABLECOIN_APY + MIN_ANNUALIZED_EDGE, signal buy.
        """
        price = opportunity.market_price
        end_date_iso = opportunity.metadata.get("end_date_iso")
        if not end_date_iso:
            return None

        try:
            end_dt = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

        now = datetime.now(tz=timezone.utc)
        days_to_resolution = (end_dt - now).total_seconds() / 86400
        if days_to_resolution <= 0:
            return None

        # Gross return if market resolves YES: buy at price, receive $1
        gross_return = (1.0 / price) - 1.0
        annualized_return = gross_return * (365.0 / days_to_resolution)

        required_return = self.STABLECOIN_APY + self.MIN_ANNUALIZED_EDGE
        if annualized_return < required_return:
            return None

        tokens = opportunity.metadata.get("tokens", [])
        token_id = self._find_token(tokens, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=0.98,
            market_price=price,
            confidence=self.CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "annualized_return": round(annualized_return, 4),
                "stablecoin_apy": self.STABLECOIN_APY,
                "days_to_resolution": round(days_to_resolution, 2),
            },
        )

    @staticmethod
    def _find_token(tokens: list, outcome: str) -> Optional[str]:
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
