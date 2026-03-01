# strategies/tier_s/s04_cross_platform_arb.py
"""
S04: Cross-Platform Arbitrage

Find same event on Polymarket and Kalshi. If YES_poly + NO_kalshi < $1.00
(after fees), risk-free arbitrage.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CrossPlatformArb(BaseStrategy):
    name = "s04_cross_platform_arb"
    tier = "S"
    strategy_id = 4
    required_data = ["kalshi"]

    POLYMARKET_FEE = 0.0001  # ~0.01%
    KALSHI_FEE = 0.007       # ~0.7%
    MIN_ARB_EDGE = 0.02      # 2% minimum after fees

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        # In production: match Polymarket markets with Kalshi events
        # For now: scan for markets that commonly exist on both platforms
        opportunities = []
        for m in markets:
            yes_price = self._get_yes_price(m)
            if yes_price is not None and m.volume > 5000:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={"tokens": m.tokens, "platform": "polymarket"},
                ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        poly_yes = opportunity.market_price

        # In production: fetch Kalshi NO price for matching event via data/kalshi.py
        # Placeholder: check if arbitrage conditions could exist
        kalshi_no = self._get_kalshi_no_price(opportunity.question)
        if kalshi_no is None:
            return None

        total_cost = poly_yes + kalshi_no + self.POLYMARKET_FEE + self.KALSHI_FEE
        arb_profit = 1.0 - total_cost

        if arb_profit < self.MIN_ARB_EDGE:
            return None

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=1.0,  # Arb = guaranteed
            market_price=poly_yes,
            confidence=0.95,
            strategy_name=self.name,
            metadata={"kalshi_no": kalshi_no, "arb_profit": arb_profit},
        )

    def _get_kalshi_no_price(self, question: str) -> Optional[float]:
        kalshi = self.get_data("kalshi")
        if kalshi is not None:
            markets = kalshi.get_markets()
            if markets:
                match = kalshi.match_polymarket_to_kalshi(question, markets)
                if match:
                    # Get NO price from Kalshi (1 - YES bid)
                    yes_bid = match.get("yes_bid", 0)
                    if yes_bid and yes_bid > 0:
                        return 1.0 - (yes_bid / 100.0)  # Kalshi prices in cents
        return None  # Original fallback

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        # Execute Polymarket side
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=size,
            strategy_name=self.name,
        )
