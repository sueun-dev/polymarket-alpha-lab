# strategies/tier_c/s93_tournament_signal.py
"""
S93: Prediction Tournament Signals

Cross-reference Polymarket prices with consensus probabilities from
prediction tournaments (Metaculus, Manifold Markets).  When the
tournament leaderboard's consensus diverges meaningfully from
Polymarket pricing, follow the tournament crowd.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class TournamentSignal(BaseStrategy):
    name = "s93_tournament_signal"
    tier = "C"
    strategy_id = 93
    required_data = []

    TOURNAMENT_KEYWORDS = ["metaculus", "manifold"]
    MIN_EDGE = 0.05

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets tracked by Metaculus or Manifold."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            if not self._tracked_by_tournament(m):
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _tracked_by_tournament(self, market: Market) -> bool:
        desc = market.description.lower()
        return any(kw in desc for kw in self.TOURNAMENT_KEYWORDS)

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Use tournament leaderboard consensus as fair probability."""
        tournament_prob = opportunity.metadata.get("tournament_consensus")
        if tournament_prob is None:
            return None

        edge = tournament_prob - opportunity.market_price
        if abs(edge) < self.MIN_EDGE:
            return None

        side = "buy" if edge > 0 else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=tournament_prob,
            market_price=opportunity.market_price,
            confidence=0.55,
            strategy_name=self.name,
            metadata={"tournament_consensus": tournament_prob, "edge": edge},
        )

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        for t in opportunity.metadata.get("tokens", []):
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
