# strategies/tier_b/s54_papal_anti_favorite.py
"""
S54: Anti-Favorite Strategy for Multi-Candidate Markets

In multi-outcome markets (papal elections, primaries, etc.), the top 2-3
favorites are typically overpriced because retail bettors pile into
recognizable names. This strategy buys NO on the combined favorites when
they exceed a threshold, capturing value from the systematic over-weighting.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class PapalAntiFavorite(BaseStrategy):
    name = "s54_papal_anti_favorite"
    tier = "B"
    strategy_id = 54
    required_data = []

    MULTI_CANDIDATE_KEYWORDS = [
        "pope", "papal", "conclave", "nominee", "primary", "winner",
        "next president", "next leader", "who will win", "election",
    ]
    FAVORITES_COMBINED_THRESHOLD = 0.50  # Act when top candidates > 50% combined
    NUM_TOP_CANDIDATES = 3               # How many favorites to consider
    ESTIMATED_OVERPRICING = 0.08         # Favorites are ~8% overpriced historically
    MIN_CONFIDENCE = 0.55

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find multi-outcome markets where top candidates are > 50% combined."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_multi_candidate = any(kw in q_lower for kw in self.MULTI_CANDIDATE_KEYWORDS)
            if not is_multi_candidate:
                continue
            # Multi-outcome markets have more than 2 tokens
            if len(m.tokens) < 3:
                continue
            sorted_tokens = sorted(
                m.tokens,
                key=lambda t: float(t.get("price", 0)),
                reverse=True,
            )
            top_prices = [float(t.get("price", 0)) for t in sorted_tokens[:self.NUM_TOP_CANDIDATES]]
            combined = sum(top_prices)
            if combined < self.FAVORITES_COMBINED_THRESHOLD:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=combined,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "top_candidates": sorted_tokens[:self.NUM_TOP_CANDIDATES],
                    "combined_price": combined,
                },
            ))
        return opportunities

    def _get_favorite_token(self, opportunity: Opportunity) -> Optional[dict]:
        """Get the single highest-priced candidate token."""
        top_candidates = opportunity.metadata.get("top_candidates", [])
        if not top_candidates:
            return None
        return top_candidates[0]

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Buy NO on the top favorite -- favorites are systematically overpriced."""
        favorite = self._get_favorite_token(opportunity)
        if not favorite:
            return None

        fav_price = float(favorite.get("price", 0))
        if fav_price <= 0:
            return None

        # The NO price on the favorite
        no_price = 1 - fav_price
        # We estimate the true NO probability is higher (favorite overpriced)
        estimated_no_prob = no_price + self.ESTIMATED_OVERPRICING

        edge = estimated_no_prob - no_price
        if edge <= 0:
            return None

        # We need a NO token ID. In multi-candidate markets, each candidate
        # has its own YES token. To short a candidate we conceptually buy NO.
        # Polymarket multi-outcome markets use conditional tokens; we use the
        # favorite's token_id and set side to "sell" (equivalent to NO).
        token_id = favorite.get("token_id", "")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="sell",
            estimated_prob=estimated_no_prob,
            market_price=no_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "favorite_name": favorite.get("outcome", "unknown"),
                "favorite_price": fav_price,
                "combined_top_price": opportunity.metadata.get("combined_price", 0),
                "edge": edge,
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
