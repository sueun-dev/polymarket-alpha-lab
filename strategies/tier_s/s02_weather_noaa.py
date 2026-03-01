# strategies/tier_s/s02_weather_noaa.py
"""
S02: Weather NOAA Arbitrage

Use NOAA weather data to find mispriced weather prediction markets.
Casual traders price by gut feeling; NOAA data gives precise probabilities.
"""
import re
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class WeatherNOAA(BaseStrategy):
    name = "s02_weather_noaa"
    tier = "S"
    strategy_id = 2
    required_data = ["noaa"]

    WEATHER_KEYWORDS = [
        "temperature", "weather", "degrees", "celsius", "fahrenheit",
        "rain", "snow", "high", "low",
    ]
    MIN_EDGE = 0.05
    MAX_BET = 3.0  # $3 micro bets

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            q_lower = m.question.lower()
            is_weather = any(kw in q_lower for kw in self.WEATHER_KEYWORDS)
            if is_weather and m.active:
                yes_price = self._get_yes_price(m)
                if yes_price is not None and yes_price < 0.15:  # Cheap YES contracts
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

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        # In production, this would query NOAA API for actual forecast
        # For now, flag opportunities where cheap YES contracts may be underpriced
        market_price = opportunity.market_price

        # Placeholder: estimate probability from question context
        # Real implementation: compare NOAA forecast vs market price
        estimated_prob = self._estimate_weather_prob(opportunity)
        if estimated_prob is None:
            return None

        edge = estimated_prob - market_price
        if edge < self.MIN_EDGE:
            return None

        yes_token_id = self._get_yes_token_id(opportunity)
        if not yes_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=yes_token_id,
            side="buy",
            estimated_prob=estimated_prob,
            market_price=market_price,
            confidence=0.6,
            strategy_name=self.name,
        )

    def _estimate_weather_prob(self, opportunity: Opportunity) -> Optional[float]:
        noaa = self.get_data("noaa_weather")
        if noaa is not None:
            city = noaa.extract_city_from_question(opportunity.question)
            if city:
                q_lower = opportunity.question.lower()
                # Try temperature-based probability
                if any(kw in q_lower for kw in ["temperature", "degrees", "fahrenheit", "celsius", "hot", "cold", "high", "low"]):
                    # Extract threshold from question (simple pattern matching)
                    threshold = self._extract_temperature(q_lower)
                    if threshold is not None:
                        above = "above" in q_lower or "exceed" in q_lower or "over" in q_lower or "high" in q_lower
                        prob = noaa.temperature_probability(city, threshold, above=above)
                        if prob is not None:
                            return prob
                # Try precipitation-based probability
                if any(kw in q_lower for kw in ["rain", "snow", "precipitation", "storm"]):
                    prob = noaa.precipitation_probability(city)
                    if prob is not None:
                        return prob

        # Original fallback
        price = opportunity.market_price
        if price < 0.05:
            return price + 0.10  # Assume some underpricing
        return None

    @staticmethod
    def _extract_temperature(text: str) -> Optional[float]:
        """Extract a temperature threshold from question text."""
        match = re.search(r'(\d+)\s*(?:°|degrees?|f|fahrenheit)', text)
        if match:
            return float(match.group(1))
        return None

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        # Cap at MAX_BET for micro-betting
        capped_size = min(size, self.MAX_BET / signal.market_price) if signal.market_price > 0 else 0
        if capped_size <= 0:
            return None
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=capped_size,
            strategy_name=self.name,
        )
