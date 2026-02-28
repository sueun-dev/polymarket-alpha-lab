# strategies/tier_a/s25_liquidity_reward.py
"""
S25: Liquidity Reward Optimization

Polymarket distributes daily USDC liquidity rewards based on Q-scores.
Q-score rewards tighter spreads, larger order sizes, and time-in-market.
This strategy targets new or low-competition markets and places quotes
near the midpoint to maximise the Q-score reward share.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class LiquidityReward(BaseStrategy):
    name = "s25_liquidity_reward"
    tier = "A"
    strategy_id = 25
    required_data = []

    MAX_LIQUIDITY = 50_000     # Target low-competition markets
    SPREAD_HALF_WIDTH = 0.02   # 2-cent spread each side of midpoint
    MIN_CONFIDENCE = 0.50

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find new or low-competition markets suitable for liquidity provision."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if m.liquidity > self.MAX_LIQUIDITY:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "liquidity": m.liquidity},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_token_ids(self, opportunity: Opportunity) -> tuple[Optional[str], Optional[str]]:
        """Return (yes_token_id, no_token_id)."""
        yes_id, no_id = None, None
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            outcome = t.get("outcome", "").lower()
            if outcome == "yes":
                yes_id = t.get("token_id", "")
            elif outcome == "no":
                no_id = t.get("token_id", "")
        return yes_id, no_id

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Calculate optimal quote placement near midpoint for max rewards."""
        yes_price = opportunity.market_price
        midpoint = yes_price  # Current YES price as midpoint estimate

        # Place a buy-YES order just below midpoint to earn Q-score
        bid_price = round(midpoint - self.SPREAD_HALF_WIDTH, 2)
        if bid_price <= 0 or bid_price >= 1:
            return None

        yes_token_id, _ = self._get_token_ids(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=midpoint,
            market_price=bid_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "midpoint": midpoint,
                "bid": bid_price,
                "ask": round(midpoint + self.SPREAD_HALF_WIDTH, 2),
                "liquidity": opportunity.metadata.get("liquidity", 0),
            },
        )

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
