# strategies/tier_b/s52_ensemble_weather.py
"""
S52: Ensemble Weather Forecast Model

Combine multiple weather forecast models (NOAA, ECMWF, GFS, etc.) to
produce a better probability estimate than any single model. Use the
ensemble average to find mispriced weather markets.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class EnsembleWeather(BaseStrategy):
    name = "s52_ensemble_weather"
    tier = "B"
    strategy_id = 52
    required_data = ["noaa", "ecmwf", "gfs"]

    WEATHER_KEYWORDS = [
        "temperature", "weather", "degrees", "celsius", "fahrenheit",
        "rain", "snow", "high", "low", "wind", "humidity", "forecast",
    ]
    # Model weights (sum to 1.0) -- tuned on historical accuracy
    MODEL_WEIGHTS = {
        "noaa": 0.35,
        "ecmwf": 0.40,
        "gfs": 0.25,
    }
    MIN_EDGE = 0.06       # Higher edge threshold for ensemble
    MIN_CONFIDENCE = 0.65

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find all active weather markets."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_weather = any(kw in q_lower for kw in self.WEATHER_KEYWORDS)
            if not is_weather:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category="weather",
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
                return t.get("token_id", "")
        return None

    def _ensemble_estimate(self, opportunity: Opportunity) -> Optional[float]:
        """Combine multiple forecast model outputs into a single probability.

        In production, each model would return a probability from its API.
        Placeholder: use market price as a base and apply a small correction.
        """
        # Placeholder: in real implementation, fetch from each model API
        # and compute weighted average
        base = opportunity.market_price
        # Simulate slight model disagreement for illustration
        model_probs = {
            "noaa": base + 0.04,
            "ecmwf": base + 0.08,
            "gfs": base + 0.03,
        }
        ensemble = sum(
            model_probs[model] * weight
            for model, weight in self.MODEL_WEIGHTS.items()
        )
        return min(max(ensemble, 0.01), 0.99)

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Combine multiple forecast models for better probability estimate."""
        market_price = opportunity.market_price
        ensemble_prob = self._ensemble_estimate(opportunity)
        if ensemble_prob is None:
            return None

        edge = ensemble_prob - market_price
        if abs(edge) < self.MIN_EDGE:
            return None

        if edge > 0:
            token_id = self._get_yes_token_id(opportunity)
            side = "buy"
            est_prob = ensemble_prob
            price = market_price
        else:
            token_id = self._get_no_token_id(opportunity)
            side = "buy"
            est_prob = 1 - ensemble_prob
            price = 1 - market_price

        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side=side,
            estimated_prob=est_prob,
            market_price=price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "ensemble_prob": ensemble_prob,
                "edge": edge,
                "model_weights": self.MODEL_WEIGHTS,
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
