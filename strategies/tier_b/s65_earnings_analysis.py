# strategies/tier_b/s65_earnings_analysis.py
"""
S65: Deep Earnings Analysis Beyond Streaks

Go deeper than simple beat/miss streaks.  Analyse revenue trends,
guidance quality, sector rotation, margin expansion, and management
credibility to estimate the probability of an earnings beat more
accurately than the market.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class DeepEarningsAnalysis(BaseStrategy):
    name = "s65_earnings_analysis"
    tier = "B"
    strategy_id = 65
    required_data = ["earnings"]

    EARNINGS_KEYWORDS = [
        "earnings", "revenue", "eps", "beat", "miss",
        "quarter", "q1", "q2", "q3", "q4", "guidance",
        "profit", "income", "report",
    ]
    MIN_EDGE = 0.05
    # Weights for composite scoring
    REVENUE_TREND_WEIGHT = 0.30
    GUIDANCE_QUALITY_WEIGHT = 0.25
    SECTOR_WEIGHT = 0.20
    MARGIN_WEIGHT = 0.25

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find earnings-related markets by keyword matching."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_earnings = any(kw in q_lower for kw in self.EARNINGS_KEYWORDS)
            if not is_earnings:
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
        """Composite earnings analysis with multiple factors.

        In production this would:
        1. Pull revenue growth trend (accelerating/decelerating)
        2. Evaluate management guidance quality (conservative vs optimistic)
        3. Check sector tailwinds/headwinds
        4. Analyse gross/operating margin trajectory
        5. Combine into weighted probability estimate
        """
        revenue_score = opportunity.metadata.get("revenue_trend_score")
        guidance_score = opportunity.metadata.get("guidance_quality_score")
        sector_score = opportunity.metadata.get("sector_score")
        margin_score = opportunity.metadata.get("margin_score")

        # All scores must be present (0.0 - 1.0 range)
        if any(s is None for s in [revenue_score, guidance_score, sector_score, margin_score]):
            return None

        composite = (
            revenue_score * self.REVENUE_TREND_WEIGHT
            + guidance_score * self.GUIDANCE_QUALITY_WEIGHT
            + sector_score * self.SECTOR_WEIGHT
            + margin_score * self.MARGIN_WEIGHT
        )
        estimated_prob = max(0.0, min(1.0, composite))
        edge = estimated_prob - opportunity.market_price

        if edge < self.MIN_EDGE:
            return None

        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=opportunity.market_price,
            confidence=0.55,
            strategy_name=self.name,
            metadata={
                "composite_score": composite,
                "revenue_score": revenue_score,
                "guidance_score": guidance_score,
                "sector_score": sector_score,
                "margin_score": margin_score,
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
