# strategies/tier_c/s94_volatility_surface.py
"""
S94: Volatility Surface Analysis

Analyse related markets at different time horizons to construct a
term-structure (volatility surface).  If the implied volatility at
one tenor is out of line with the rest of the curve, there is a
trading opportunity.
"""
from typing import Dict, List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class VolatilitySurface(BaseStrategy):
    name = "s94_volatility_surface"
    tier = "C"
    strategy_id = 94
    required_data = []

    MIN_TENORS = 2
    MIN_EDGE = 0.04

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find related markets at different time horizons."""
        groups: Dict[str, List[Market]] = {}
        for m in markets:
            if not m.active or not m.end_date_iso:
                continue
            stem = self._extract_stem(m.question)
            if stem:
                groups.setdefault(stem, []).append(m)

        opportunities: List[Opportunity] = []
        for stem, group in groups.items():
            if len(group) < self.MIN_TENORS:
                continue
            for m in group:
                yes_price = self._get_yes_price(m)
                if yes_price is None:
                    continue
                peer_prices = []
                for peer in group:
                    if peer.condition_id == m.condition_id:
                        continue
                    pp = self._get_yes_price(peer)
                    if pp is not None:
                        peer_prices.append(pp)
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "peer_prices": peer_prices,
                        "end_date": m.end_date_iso,
                    },
                ))
        return opportunities

    @staticmethod
    def _extract_stem(question: str) -> str:
        q = question.lower().strip().rstrip("?").strip()
        words = q.split()
        stem_words = []
        for w in words:
            cleaned = w.replace(",", "").replace("$", "").replace("k", "")
            try:
                float(cleaned)
                continue
            except ValueError:
                stem_words.append(w)
        return " ".join(stem_words) if len(stem_words) >= 3 else ""

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Term structure analysis: flag mis-priced tenors."""
        peer_prices = opportunity.metadata.get("peer_prices", [])
        if not peer_prices:
            return None

        avg_peer = sum(peer_prices) / len(peer_prices)
        edge = avg_peer - opportunity.market_price
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
            estimated_prob=avg_peer,
            market_price=opportunity.market_price,
            confidence=0.45,
            strategy_name=self.name,
            metadata={"avg_peer_price": avg_peer, "edge": edge},
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
