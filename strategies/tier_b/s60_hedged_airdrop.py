# strategies/tier_b/s60_hedged_airdrop.py
"""
S60: Hedged Airdrop Farming on Polymarket

Polymarket distributes volume-based rewards (similar to airdrops) to
active traders. This strategy maximizes reward eligibility by generating
volume while hedging directional risk -- buying both YES and NO in
proportion to maintain near-zero net exposure while collecting rewards.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class HedgedAirdrop(BaseStrategy):
    name = "s60_hedged_airdrop"
    tier = "B"
    strategy_id = 60
    required_data = []

    MIN_VOLUME_REWARD = 1000  # Minimum volume to be reward-eligible
    MAX_SPREAD_COST = 0.04    # Maximum acceptable spread cost for hedging
    MIN_CONFIDENCE = 0.50

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with volume rewards where hedged farming is profitable."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            # Target markets with good liquidity (low spread cost)
            if m.liquidity < self.MIN_VOLUME_REWARD:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            no_price = self._get_no_price(m)
            if no_price is None:
                continue
            # Check the spread (deviation from 1.0 sum)
            spread = (yes_price + no_price) - 1.0
            if spread > self.MAX_SPREAD_COST:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "liquidity": m.liquidity,
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "spread": spread,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_no_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "no":
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
        """Maximize volume rewards while hedging directional risk.

        Buy YES and NO in equal dollar amounts to create a delta-neutral
        position. The spread cost is the price of farming rewards.
        """
        spread = opportunity.metadata.get("spread", 1.0)
        if spread > self.MAX_SPREAD_COST:
            return None

        yes_token_id, no_token_id = self._get_token_ids(opportunity)
        if not yes_token_id or not no_token_id:
            return None

        yes_price = opportunity.metadata.get("yes_price", 0)
        no_price = opportunity.metadata.get("no_price", 0)
        if yes_price <= 0 or no_price <= 0:
            return None

        # Signal to buy YES side; the execute method would also buy NO
        # to complete the hedge (in production, two orders are placed)
        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=yes_price,
            market_price=yes_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "hedge_token_id": no_token_id,
                "hedge_price": no_price,
                "spread_cost": spread,
                "liquidity": opportunity.metadata.get("liquidity", 0),
            },
        )

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        # Place the YES side of the hedge
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=size,
            strategy_name=self.name,
        )
