# strategies/tier_s/s02_weather_noaa.py
"""
S02: Weather NOAA Arbitrage

Use NOAA weather data to find mispriced weather prediction markets.
Casual traders price by gut feeling; NOAA data gives precise probabilities.
"""
import math
import re
from datetime import date, datetime
from typing import List, Optional, Tuple

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order
from core.native_weather_kernel import NativeS02WeatherKernel


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
    TEMP_SIGMA_F = 2.2  # Conservative daily-high forecast error band
    _kernel: Optional[NativeS02WeatherKernel] = None

    def _kernel_instance(self) -> NativeS02WeatherKernel:
        if WeatherNOAA._kernel is None:
            WeatherNOAA._kernel = NativeS02WeatherKernel()
        return WeatherNOAA._kernel

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
                        metadata={
                            "tokens": m.tokens,
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

    @staticmethod
    def _yes_no_from_tokens(tokens: List[dict]) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        yes_price = None
        no_price = None
        yes_token = None
        no_token = None
        for token in tokens:
            outcome = str(token.get("outcome", "")).strip().lower()
            token_id = str(token.get("token_id", token.get("tokenId", ""))).strip()
            try:
                price = float(token.get("price", 0))
            except Exception:
                continue
            if not (0.0 <= price <= 1.0):
                continue
            if outcome == "yes":
                yes_price = price
                yes_token = token_id or None
            elif outcome == "no":
                no_price = price
                no_token = token_id or None
        if yes_price is not None and no_price is None:
            no_price = 1.0 - yes_price
        if no_price is not None and yes_price is None:
            yes_price = 1.0 - no_price
        return yes_price, no_price, yes_token, no_token

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        estimation = self._estimate_weather_prob_and_confidence(opportunity)
        if estimation is None:
            return None
        estimated_yes_prob, confidence = estimation

        tokens = opportunity.metadata.get("tokens", [])
        yes_price, no_price, yes_token_id, no_token_id = self._yes_no_from_tokens(tokens)
        if yes_price is None or no_price is None:
            return None
        if yes_token_id is None and no_token_id is None:
            return None

        estimated_no_prob = 1.0 - estimated_yes_prob
        yes_edge = estimated_yes_prob - yes_price
        no_edge = estimated_no_prob - no_price
        if yes_edge < self.MIN_EDGE and no_edge < self.MIN_EDGE:
            return None

        buy_yes = yes_edge >= no_edge
        token_id = yes_token_id if buy_yes else no_token_id
        if token_id is None:
            token_id = no_token_id if buy_yes else yes_token_id
        if token_id is None:
            return None

        chosen_estimated_prob = estimated_yes_prob if buy_yes else estimated_no_prob
        chosen_market_price = yes_price if buy_yes else no_price
        chosen_edge = yes_edge if buy_yes else no_edge

        city = opportunity.metadata.get("city", "")
        weather_type = opportunity.metadata.get("weather_type", "")

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=chosen_estimated_prob,
            market_price=chosen_market_price,
            confidence=confidence,
            strategy_name=self.name,
            metadata={
                "edge": chosen_edge,
                "yes_edge": yes_edge,
                "no_edge": no_edge,
                "model": "s02_native_weather_kernel",
                "native_enabled": self._kernel_instance().native_enabled,
                "weather_type": weather_type,
                "city": city,
                "side_selected": "yes" if buy_yes else "no",
            },
        )

    def _estimate_weather_prob(self, opportunity: Opportunity) -> Optional[float]:
        estimation = self._estimate_weather_prob_and_confidence(opportunity)
        if estimation is None:
            return None
        return estimation[0]

    def _estimate_weather_prob_and_confidence(self, opportunity: Opportunity) -> Optional[Tuple[float, float]]:
        noaa = self.get_data("noaa_weather") or self.get_data("noaa")
        if noaa is not None:
            city = noaa.extract_city_from_question(opportunity.question)
            if city:
                opportunity.metadata["city"] = city
                q_lower = opportunity.question.lower()
                forecast = noaa.get_forecast(city)
                if forecast:
                    horizon_hours = self._extract_horizon_hours(q_lower)
                    target_date = self._extract_target_date(opportunity.question)
                    periods = self._select_periods_for_target(forecast, target_date, horizon_hours=horizon_hours)

                    # Temperature contracts:
                    # 1) threshold style (above/exceed N)
                    # 2) range style (between A-B, N or below/higher, exact N)
                    if any(kw in q_lower for kw in ["temperature", "degrees", "fahrenheit", "celsius", "hot", "cold", "high", "low"]):
                        opportunity.metadata["weather_type"] = "temperature"
                        temps = self._extract_temperatures(periods)
                        if temps:
                            contract = self._extract_temperature_contract(q_lower)
                            if contract is not None:
                                prob_yes = self._temperature_contract_probability(
                                    mu=max(temps),
                                    sigma=max(0.8, float(self.TEMP_SIGMA_F)),
                                    contract=contract,
                                )
                                sample_score = min(1.0, math.sqrt(len(temps) / 24.0))
                                confidence = max(0.35, min(0.95, 0.50 + (abs(prob_yes - 0.5) * 0.35) + (sample_score * 0.10)))
                                return prob_yes, confidence

                            threshold = self._extract_temperature(q_lower)
                            if threshold is not None:
                                above = "above" in q_lower or "exceed" in q_lower or "over" in q_lower or "higher" in q_lower
                                return self._kernel_instance().temperature_probability(temps, threshold, above=above)

                    # Precipitation contracts (e.g., rain/snow)
                    if any(kw in q_lower for kw in ["rain", "snow", "precipitation", "storm"]):
                        opportunity.metadata["weather_type"] = "precipitation"
                        pops = []
                        for period in periods:
                            pop_obj = period.get("probabilityOfPrecipitation")
                            value = 0.0
                            if isinstance(pop_obj, dict):
                                raw = pop_obj.get("value")
                                if raw is not None:
                                    try:
                                        value = float(raw)
                                    except Exception:
                                        value = 0.0
                            pops.append(value)
                        if pops:
                            return self._kernel_instance().precipitation_probability(pops)

        # Compatibility fallback: preserve previous behavior when NOAA parse fails.
        price = opportunity.market_price
        if price < 0.05:
            return price + 0.10, 0.40  # Assume some underpricing
        return None

    @staticmethod
    def _extract_temperature(text: str) -> Optional[float]:
        """Extract a temperature threshold from question text."""
        match = re.search(r'(\d+)\s*(?:°|degrees?|f|fahrenheit)', text)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _extract_target_date(text: str) -> Optional[date]:
        month_map = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }
        q = text.lower()
        m = re.search(r"on\s+([a-z]+)\s+(\d{1,2})(?:,?\s*(\d{4}))?", q)
        if not m:
            return None
        month = month_map.get(m.group(1))
        if month is None:
            return None
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.utcnow().year
        try:
            return date(year, month, day)
        except Exception:
            return None

    @staticmethod
    def _period_date(period: dict) -> Optional[date]:
        start = period.get("startTime")
        if not start:
            return None
        try:
            return datetime.fromisoformat(str(start).replace("Z", "+00:00")).date()
        except Exception:
            return None

    def _select_periods_for_target(self, forecast: List[dict], target_date: Optional[date], horizon_hours: int) -> List[dict]:
        if target_date is not None:
            selected = [p for p in forecast if self._period_date(p) == target_date]
            if selected:
                return selected
        return forecast[:horizon_hours]

    @staticmethod
    def _extract_temperatures(periods: List[dict]) -> List[float]:
        out: List[float] = []
        for period in periods:
            raw = period.get("temperature")
            if raw is None:
                continue
            try:
                out.append(float(raw))
            except Exception:
                continue
        return out

    @staticmethod
    def _extract_temperature_contract(text: str) -> Optional[Tuple[str, float, Optional[float]]]:
        text = text.lower()
        unit = r"(?:°\s*[fc]|degrees?|fahrenheit|celsius|f|c)?"
        # between A-B
        m_between = re.search(r"between\s+(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)", text)
        if m_between:
            lo = float(m_between.group(1))
            hi = float(m_between.group(2))
            if lo > hi:
                lo, hi = hi, lo
            return "between", lo, hi

        # "N or below/lower/less"
        m_below = re.search(rf"(-?\d+(?:\.\d+)?)\s*{unit}\s*or\s*(?:below|lower|less|under)", text)
        if m_below:
            return "le", float(m_below.group(1)), None

        # "N or higher/above/more/over"
        m_above = re.search(rf"(-?\d+(?:\.\d+)?)\s*{unit}\s*or\s*(?:higher|above|more|over)", text)
        if m_above:
            return "ge", float(m_above.group(1)), None

        # exact: "be N°C on ..."
        m_exact = re.search(rf"be\s+(-?\d+(?:\.\d+)?)\s*{unit}\s+on\b", text)
        if m_exact:
            return "eq", float(m_exact.group(1)), None
        return None

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _temperature_contract_probability(self, mu: float, sigma: float, contract: Tuple[str, float, Optional[float]]) -> float:
        ctype, a, b = contract
        if sigma <= 0:
            sigma = 1.0

        def cdf(v: float) -> float:
            return self._normal_cdf((v - mu) / sigma)

        if ctype == "between" and b is not None:
            lo = a - 0.5
            hi = b + 0.5
            return max(0.0, min(1.0, cdf(hi) - cdf(lo)))
        if ctype == "le":
            return max(0.0, min(1.0, cdf(a + 0.5)))
        if ctype == "ge":
            return max(0.0, min(1.0, 1.0 - cdf(a - 0.5)))
        if ctype == "eq":
            return max(0.0, min(1.0, cdf(a + 0.5) - cdf(a - 0.5)))
        return 0.5

    @staticmethod
    def _extract_horizon_hours(text: str) -> int:
        """Infer forecast window from question text."""
        if "tomorrow" in text:
            return 24
        hour_match = re.search(r'next\s+(\d{1,2})\s*hours?', text)
        if hour_match:
            try:
                value = int(hour_match.group(1))
            except Exception:
                value = 24
            return max(1, min(value, 48))
        return 24

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
