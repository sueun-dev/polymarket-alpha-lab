# strategies/tier_b/s61_volmex_volatility.py
"""
S61: Volmex Implied Volatility Trading

Trade Volmex implied volatility markets by comparing implied vol (from
market prices) to historical realised vol. When the market overprices or
underprices future volatility relative to the historical baseline, take
a directional position.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class VolmexVolatilityTrading(BaseStrategy):
    name = "s61_volmex_volatility"
    tier = "B"
    strategy_id = 61
    required_data = ["volatility"]

    VOL_KEYWORDS = [
        "volatility", "vol", "vix", "volmex", "implied vol",
        "realized vol", "iv", "hvol",
    ]
    MIN_EDGE = 0.05
    HISTORICAL_VOL_DEFAULT = 0.50  # Default annualised historical vol assumption

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with volatility-related keywords."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_vol = any(kw in q_lower for kw in self.VOL_KEYWORDS)
            if not is_vol:
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
        """Compare implied vol (market price) to historical vol.

        In production this would:
        1. Fetch realised volatility data from on-chain / off-chain feeds
        2. Compute implied volatility from the market price
        3. If implied vol significantly differs from historical vol, trade
        """
        implied_vol = opportunity.metadata.get("implied_vol")
        historical_vol = opportunity.metadata.get(
            "historical_vol", self.HISTORICAL_VOL_DEFAULT,
        )
        if implied_vol is None:
            return None

        # If implied vol is much higher than historical -> sell vol (buy NO)
        # If implied vol is much lower than historical -> buy vol (buy YES)
        vol_diff = implied_vol - historical_vol
        if abs(vol_diff) < self.MIN_EDGE:
            return None

        side = "buy"
        if vol_diff > 0:
            # Implied vol overpriced -> sell vol -> buy NO side
            estimated_prob = max(0.0, opportunity.market_price - abs(vol_diff))
        else:
            # Implied vol underpriced -> buy vol -> buy YES side
            estimated_prob = min(1.0, opportunity.market_price + abs(vol_diff))

        edge = abs(estimated_prob - opportunity.market_price)
        if edge < self.MIN_EDGE:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.50,
            strategy_name=self.name,
            metadata={
                "implied_vol": implied_vol,
                "historical_vol": historical_vol,
                "vol_diff": vol_diff,
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
