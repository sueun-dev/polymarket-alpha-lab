# strategies/tier_c/s87_ml_features.py
"""
S87: ML Feature Engineering Pipeline

Scan all active markets and extract a standardised feature vector for
each one (price, volume, liquidity, category encoding, etc.).  The
analyze step is a placeholder for downstream ML model inference.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class MLFeatureEngineering(BaseStrategy):
    name = "s87_ml_features"
    tier = "C"
    strategy_id = 87
    required_data = []

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Extract feature vectors for every active market."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            features = {
                "price": yes_price,
                "volume": m.volume,
                "liquidity": m.liquidity,
                "category": m.category,
                "question_length": len(m.question),
            }
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "features": features},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder: run ML model on feature vector."""
        features = opportunity.metadata.get("features")
        if not features:
            return None

        ml_prediction = opportunity.metadata.get("ml_prediction")
        if ml_prediction is None:
            return None

        edge = ml_prediction - opportunity.market_price
        if abs(edge) < 0.03:
            return None

        side = "buy" if edge > 0 else "sell"
        token_id = self._get_token_id(opportunity, "yes")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=ml_prediction,
            market_price=opportunity.market_price,
            confidence=0.40,
            strategy_name=self.name,
            metadata={"features": features, "ml_prediction": ml_prediction},
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
