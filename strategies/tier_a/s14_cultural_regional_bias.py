# strategies/tier_a/s14_cultural_regional_bias.py
"""
S14: Cultural Regional Bias

Non-US events are systematically mispriced because the majority of Polymarket
users are American. Markets about European, Asian, or other non-US events tend
to have less informed trading, creating opportunities for anyone with regional
knowledge. Flag these markets for manual review with higher estimated edge.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CulturalRegionalBias(BaseStrategy):
    name = "s14_cultural_regional_bias"
    tier = "A"
    strategy_id = 14
    required_data = []

    # Keywords indicating non-US markets
    NON_US_KEYWORDS = [
        # Regions
        "europe", "european", "asia", "asian", "africa", "african",
        "middle east", "latin america", "south america",
        # Countries
        "france", "french", "germany", "german", "japan", "japanese",
        "korea", "korean", "uk", "united kingdom", "britain", "british",
        "australia", "australian", "canada", "canadian",
        "india", "indian", "china", "chinese", "brazil", "brazilian",
        "mexico", "mexican", "russia", "russian", "italy", "italian",
        "spain", "spanish", "netherlands", "dutch",
        "sweden", "swedish", "norway", "norwegian",
        "turkey", "turkish", "israel", "israeli",
        "south africa", "nigeria", "egypt", "saudi",
        # Non-US political terms
        "parliament", "prime minister", "bundesliga", "premier league",
        "serie a", "la liga", "ligue 1", "cricket", "rugby",
        "eurovision", "eu ", "nato",
    ]
    # Estimated edge multiplier for non-US markets
    BASE_EDGE_ESTIMATE = 0.08  # 8% estimated mispricing for non-US events
    MIN_VOLUME = 1000  # Minimum volume to consider

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets about non-US events."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            desc_lower = m.description.lower() if m.description else ""
            combined = q_lower + " " + desc_lower

            matched_keywords = [kw for kw in self.NON_US_KEYWORDS if kw in combined]
            if not matched_keywords:
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
                    "matched_keywords": matched_keywords,
                    "volume": m.volume,
                    "description": m.description,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Flag non-US markets for manual review with higher estimated edge."""
        yes_price = opportunity.market_price
        volume = opportunity.metadata.get("volume", 0)

        # Low volume non-US markets are more likely to be mispriced
        if volume < self.MIN_VOLUME:
            edge_boost = 0.03  # Extra 3% edge for low-volume markets
        else:
            edge_boost = 0.0

        estimated_edge = self.BASE_EDGE_ESTIMATE + edge_boost

        # We don't know direction -- flag for manual review
        # Default: assume YES is slightly overpriced (US bias tends toward YES)
        estimated_yes_prob = yes_price - estimated_edge
        estimated_yes_prob = max(0.01, min(0.99, estimated_yes_prob))

        # Only signal if there is meaningful edge
        if estimated_edge < 0.05:
            return None

        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",
            estimated_prob=1 - estimated_yes_prob,
            market_price=1 - yes_price,
            confidence=0.50,  # Lower confidence -- needs manual review
            strategy_name=self.name,
            metadata={
                "matched_keywords": opportunity.metadata.get("matched_keywords", []),
                "estimated_edge": estimated_edge,
                "requires_manual_review": True,
            },
        )

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        # Reduced size due to lower confidence / need for manual review
        adjusted_size = size * 0.5
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=adjusted_size,
            strategy_name=self.name,
        )
