# strategies/tier_a/s11_superforecaster.py
"""
S11: Superforecaster Method

Bayesian updating approach inspired by the superforecasting methodology.
Compare independent probability estimates (using base rates and outside-view
reasoning) against market prices. Require a 5%+ edge before trading.
Track calibration over time to improve estimates.
"""
from typing import List, Optional, Dict

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class SuperforecasterMethod(BaseStrategy):
    name = "s11_superforecaster"
    tier = "A"
    strategy_id = 11
    required_data = []

    MIN_EDGE = 0.05  # 5% minimum edge required
    # Base rates by category -- outside-view anchors
    CATEGORY_BASE_RATES: Dict[str, float] = {
        "politics": 0.35,
        "crypto": 0.30,
        "sports": 0.50,
        "science": 0.25,
        "economics": 0.40,
        "default": 0.35,
    }
    # Calibration tracker: stores (predicted, actual) for scoring
    calibration_log: List[Dict] = []

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets where the question is quantifiable and has a clear resolution."""
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            # Quantifiable markets: have end date, clear question, reasonable volume
            has_end_date = m.end_date_iso is not None and m.end_date_iso != ""
            is_quantifiable = self._is_quantifiable(m.question)
            if has_end_date and is_quantifiable:
                opportunities.append(Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category=m.category,
                    metadata={
                        "tokens": m.tokens,
                        "end_date_iso": m.end_date_iso,
                        "volume": m.volume,
                    },
                ))
        return opportunities

    def _is_quantifiable(self, question: str) -> bool:
        """Check if a question has a clear, measurable resolution criterion."""
        q = question.lower()
        quantifiable_markers = [
            "will", "by", "before", "above", "below", "more than",
            "less than", "at least", "reach", "exceed", "win",
        ]
        return any(marker in q for marker in quantifiable_markers)

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_base_rate(self, category: str) -> float:
        """Get the outside-view base rate for a category."""
        return self.CATEGORY_BASE_RATES.get(
            category.lower(), self.CATEGORY_BASE_RATES["default"]
        )

    def _bayesian_update(self, prior: float, yes_price: float) -> float:
        """
        Simple Bayesian update: anchor on base rate, then adjust toward
        market price but with shrinkage (we trust our base rate partially).
        """
        # Weight: 60% base rate, 40% market signal
        weight_base = 0.60
        weight_market = 0.40
        posterior = weight_base * prior + weight_market * yes_price
        return round(max(0.01, min(0.99, posterior)), 4)

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Compare independent Bayesian estimate to market price. Require 5%+ edge."""
        yes_price = opportunity.market_price
        base_rate = self._get_base_rate(opportunity.category)
        estimated_prob = self._bayesian_update(base_rate, yes_price)

        # Determine direction: do we think YES is overpriced or underpriced?
        edge_yes = estimated_prob - yes_price
        edge_no = (1 - estimated_prob) - (1 - yes_price)  # same magnitude, opposite sign

        if abs(edge_yes) < self.MIN_EDGE:
            return None

        tokens = opportunity.metadata.get("tokens", [])

        if edge_yes > 0:
            # YES is underpriced -- buy YES
            token_id = self._get_token_id(tokens, "yes")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=estimated_prob,
                market_price=yes_price,
                confidence=0.65,
                strategy_name=self.name,
                metadata={
                    "base_rate": base_rate,
                    "bayesian_estimate": estimated_prob,
                    "edge": edge_yes,
                },
            )
        else:
            # YES is overpriced -- buy NO
            token_id = self._get_token_id(tokens, "no")
            if not token_id:
                return None
            return Signal(
                market_id=opportunity.market_id,
                token_id=token_id,
                side="buy",
                estimated_prob=1 - estimated_prob,
                market_price=1 - yes_price,
                confidence=0.65,
                strategy_name=self.name,
                metadata={
                    "base_rate": base_rate,
                    "bayesian_estimate": estimated_prob,
                    "edge": abs(edge_yes),
                },
            )

    def _get_token_id(self, tokens: list, outcome: str) -> Optional[str]:
        for t in tokens:
            if t.get("outcome", "").lower() == outcome:
                return t.get("token_id", "")
        return None

    def log_calibration(self, predicted: float, actual: float):
        """Track calibration for future improvement."""
        self.calibration_log.append({"predicted": predicted, "actual": actual})

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
