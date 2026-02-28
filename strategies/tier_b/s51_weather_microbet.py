# strategies/tier_b/s51_weather_microbet.py
"""
S51: Automated Weather Micro-Bets

Place $1-$3 diversified micro-bets across cheap weather markets.
Scan for YES contracts priced under $0.15 across multiple cities,
then spread small positions to capture occasional large payoffs.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class WeatherMicroBet(BaseStrategy):
    name = "s51_weather_microbet"
    tier = "B"
    strategy_id = 51
    required_data = ["noaa"]

    WEATHER_KEYWORDS = [
        "temperature", "weather", "degrees", "celsius", "fahrenheit",
        "rain", "snow", "high", "low", "wind", "humidity", "forecast",
    ]
    CITY_KEYWORDS = [
        "new york", "los angeles", "chicago", "houston", "phoenix",
        "miami", "denver", "seattle", "boston", "dallas", "atlanta",
        "san francisco", "london", "paris", "tokyo",
    ]
    MAX_YES_PRICE = 0.15  # Only buy cheap YES contracts
    MIN_BET = 1.0         # $1 minimum bet
    MAX_BET = 3.0         # $3 maximum bet
    MIN_EDGE = 0.03       # Minimum edge to act

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find weather markets with YES < $0.15 across diverse cities."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            is_weather = any(kw in q_lower for kw in self.WEATHER_KEYWORDS)
            if not is_weather:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None or yes_price >= self.MAX_YES_PRICE:
                continue
            city = self._detect_city(q_lower)
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category="weather",
                metadata={"tokens": m.tokens, "volume": m.volume, "city": city},
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

    def _detect_city(self, question: str) -> str:
        """Detect which city a weather question relates to."""
        for city in self.CITY_KEYWORDS:
            if city in question:
                return city
        return "unknown"

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Buy diversified micro positions across cities."""
        market_price = opportunity.market_price
        # Placeholder: assume cheap weather contracts are slightly underpriced
        estimated_prob = market_price + 0.05
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
            confidence=0.55,
            strategy_name=self.name,
            metadata={
                "city": opportunity.metadata.get("city", "unknown"),
                "bet_range": [self.MIN_BET, self.MAX_BET],
            },
        )

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
