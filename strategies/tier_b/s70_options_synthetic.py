# strategies/tier_b/s70_options_synthetic.py
"""
S70: Options-Style Synthetic Positions

Construct synthetic options-like positions from YES/NO token
combinations across related markets.  For example, buying YES on
"BTC > 100K" and NO on "BTC > 120K" creates a synthetic bull-call
spread.  This strategy identifies such multi-market structures and
trades them when the combined cost is below fair value.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class OptionsSyntheticPositions(BaseStrategy):
    name = "s70_options_synthetic"
    tier = "B"
    strategy_id = 70
    required_data = []

    MIN_EDGE = 0.04
    MIN_RELATED_MARKETS = 2  # Need at least 2 markets to form a spread

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with multiple related outcomes for synthetic construction."""
        # Group markets by overlapping question stems
        groups: dict[str, list[Market]] = {}
        for m in markets:
            if not m.active:
                continue
            stem = self._extract_stem(m.question)
            if not stem:
                continue
            groups.setdefault(stem, []).append(m)

        opportunities: List[Opportunity] = []
        for stem, group in groups.items():
            if len(group) < self.MIN_RELATED_MARKETS:
                continue
            for m in group:
                yes_price = self._get_yes_price(m)
                if yes_price is None:
                    continue
                related_ids = [
                    r.condition_id for r in group if r.condition_id != m.condition_id
                ]
                related_prices = []
                for r in group:
                    if r.condition_id == m.condition_id:
                        continue
                    rp = self._get_yes_price(r)
                    if rp is not None:
                        related_prices.append(rp)

                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "volume": m.volume,
                        "related_ids": related_ids,
                        "related_prices": related_prices,
                        "stem": stem,
                    },
                ))
        return opportunities

    @staticmethod
    def _extract_stem(question: str) -> str:
        """Extract a normalised stem for grouping related questions.

        e.g. "Will BTC be above 100K?" and "Will BTC be above 120K?"
        both share the stem "will btc be above".
        """
        q = question.lower().strip().rstrip("?").strip()
        # Remove trailing numbers/dollar amounts to find the common stem
        words = q.split()
        # Drop the last word if it looks like a number/amount
        stem_words = []
        for w in words:
            cleaned = w.replace(",", "").replace("$", "").replace("k", "")
            try:
                float(cleaned)
                continue  # Skip numeric tokens
            except ValueError:
                stem_words.append(w)
        return " ".join(stem_words) if len(stem_words) >= 3 else ""

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Construct and price a synthetic options position.

        In production this would:
        1. Identify the spread type (bull call, bear put, straddle, etc.)
        2. Price each leg using current YES/NO token prices
        3. Compute the synthetic position cost
        4. Compare to theoretical fair value from an options pricing model
        5. Trade if combined cost < fair value by > MIN_EDGE
        """
        related_prices = opportunity.metadata.get("related_prices", [])
        if not related_prices:
            return None

        synthetic_cost = opportunity.metadata.get("synthetic_cost")
        fair_value = opportunity.metadata.get("fair_value")
        if synthetic_cost is None or fair_value is None:
            return None

        edge = fair_value - synthetic_cost
        if edge < self.MIN_EDGE:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=min(0.99, opportunity.market_price + edge),
            market_price=opportunity.market_price,
            confidence=0.50,
            strategy_name=self.name,
            metadata={
                "synthetic_cost": synthetic_cost,
                "fair_value": fair_value,
                "edge": edge,
                "num_legs": len(related_prices) + 1,
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
