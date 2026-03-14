# strategies/tier_s/s02_weather_noaa.py
"""
S02: Weather NOAA Arbitrage

Use NOAA weather data to find mispriced weather prediction markets.
Casual traders price by gut feeling; NOAA data gives precise probabilities.
"""
import math
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order
from core.native_weather_kernel import NativeS02WeatherKernel
from core.weather_market_engine import (
    WeatherMarketEngine,
    WeatherFairValue,
    extract_horizon_hours,
    extract_target_date,
    extract_temperature,
    extract_temperature_contract,
    extract_temperatures,
    select_periods_for_target,
    temperature_contract_probability,
)


class WeatherNOAA(BaseStrategy):
    name = "s02_weather_noaa"
    tier = "S"
    strategy_id = 2
    required_data = ["noaa"]

    WEATHER_KEYWORDS = [
        "temperature", "weather", "degrees", "celsius", "fahrenheit",
        "rain", "snow", "high", "low", "global", "increase", "hottest",
    ]
    MIN_EDGE = 0.05
    MIN_CONFIDENCE = 0.45
    LONGSHOT_YES_MAX = 0.15
    FADE_YES_MIN = 0.45
    MAX_BET = 10.0
    BASE_BET = 3.0
    TEMP_SIGMA_F = 2.2  # Conservative daily-high forecast error band
    _kernel: Optional[NativeS02WeatherKernel] = None

    WEATHER_FALLBACK_PATTERNS = [
        re.compile(r"\b(?:highest|lowest|high|low)\s+temperature\b"),
        re.compile(r"\bwill it (?:rain|snow) in\b"),
        re.compile(r"\bprecipitation in\b"),
        re.compile(r"\brecord precipitation\b"),
    ]
    CLIMATE_REPRICE_PATTERNS = [
        re.compile(r"\bglobal temperature increase\b"),
        re.compile(r"\btemperature increase by\b"),
        re.compile(r"\bhottest on record\b"),
    ]
    HOLD_MARKET_TYPES = {"temperature", "precipitation", "monthly_precipitation", "monthly_precip_days"}

    def _kernel_instance(self) -> NativeS02WeatherKernel:
        if WeatherNOAA._kernel is None:
            WeatherNOAA._kernel = NativeS02WeatherKernel()
        return WeatherNOAA._kernel

    def _engine(self, noaa_provider=None) -> WeatherMarketEngine:
        aviation = self.get_data("aviation_weather")
        climate = self.get_data("nws_climate")
        global_climate = self.get_data("global_climate")
        return WeatherMarketEngine(
            noaa_provider,
            self._kernel_instance(),
            aviation_provider=aviation,
            climate_provider=climate,
            global_climate_provider=global_climate,
        )

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        return self.scan_market_universe(markets, include_low_score=False)

    def scan_market_universe(self, markets: List[Market], include_low_score: bool = False) -> List[Opportunity]:
        noaa = self.get_data("noaa_weather") or self.get_data("noaa")
        engine = self._engine(noaa)
        opportunities = []
        for m in markets:
            if not m.active:
                continue
            yes_price, no_price, _, _ = self._yes_no_from_tokens(m.tokens)
            if yes_price is None or no_price is None:
                continue
            if not engine.is_weather_market(m.question, m.description, m.category):
                continue

            spec = engine.parse_market(
                m.question,
                description=m.description,
                end_date_iso=m.end_date_iso,
                resolution_source=m.resolution_source,
            )
            fallback_weather = False
            if spec is None:
                # Preserve prior broad scanning behavior as a fallback.
                q_lower = m.question.lower()
                fallback_weather = (
                    yes_price < self.LONGSHOT_YES_MAX
                    and any(kw in q_lower for kw in self.WEATHER_KEYWORDS)
                    and any(pattern.search(q_lower) for pattern in self.WEATHER_FALLBACK_PATTERNS)
                )
                if not include_low_score and not fallback_weather:
                    continue

            candidate_score = self._scan_score(
                yes_price=yes_price,
                no_price=no_price,
                volume=float(m.volume or 0.0),
                spec=spec,
            )
            if candidate_score <= 0 and not include_low_score:
                continue

            opportunities.append(
                Opportunity(
                    market_id=m.condition_id,
                    question=m.question,
                    market_price=yes_price,
                    category="weather",
                    metadata={
                        "tokens": m.tokens,
                        "volume": m.volume,
                        "description": m.description,
                        "end_date_iso": m.end_date_iso,
                        "resolution_source": m.resolution_source,
                        "event_id": m.event_id,
                        "tags": m.tags,
                        "candidate_score": candidate_score,
                        "scan_status": "candidate" if candidate_score > 0 else "watch_only",
                        "parse_supported": spec is not None,
                        "fallback_weather": fallback_weather,
                        "contract": spec.to_metadata() if spec is not None else None,
                    },
                )
            )
        opportunities.sort(key=lambda opp: float(opp.metadata.get("candidate_score", 0.0)), reverse=True)
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
        evaluation = self.evaluate_opportunity(opportunity)
        signal = evaluation.get("signal")
        return signal if isinstance(signal, Signal) else None

    def evaluate_opportunity(self, opportunity: Opportunity) -> Dict[str, Any]:
        fair_value = self._estimate_weather_fair_value(opportunity)
        if fair_value is None:
            return {
                "status": "blocked",
                "reason_code": "no_fair_value",
                "reason": "공정가 계산에 필요한 공식 데이터가 부족합니다.",
                "signal": None,
                "confidence": 0.0,
                "max_edge": None,
                "required_edge": None,
            }
        estimated_yes_prob = fair_value.fair_yes_prob
        confidence = fair_value.confidence
        weather_type = str(opportunity.metadata.get("weather_type", "") or fair_value.market_type)
        regime = self._market_regime(opportunity.question, weather_type)

        tokens = opportunity.metadata.get("tokens", [])
        yes_price, no_price, yes_token_id, no_token_id = self._yes_no_from_tokens(tokens)
        if yes_price is None or no_price is None:
            return {
                "status": "blocked",
                "reason_code": "missing_yes_no_prices",
                "reason": "YES/NO 가격이 완전하지 않아 실행 판단을 할 수 없습니다.",
                "signal": None,
                "confidence": confidence,
                "max_edge": None,
                "required_edge": None,
            }
        if yes_token_id is None and no_token_id is None:
            return {
                "status": "blocked",
                "reason_code": "missing_token_ids",
                "reason": "주문 가능한 token_id가 없습니다.",
                "signal": None,
                "confidence": confidence,
                "max_edge": None,
                "required_edge": None,
            }

        estimated_no_prob = 1.0 - estimated_yes_prob
        yes_edge = estimated_yes_prob - yes_price
        no_edge = estimated_no_prob - no_price
        max_edge = max(yes_edge, no_edge)
        required_edge = self._required_edge(
            yes_price=yes_price,
            no_price=no_price,
            confidence=confidence,
            regime=regime,
        )
        release_buffer = self._release_buffer(fair_value=fair_value, regime=regime)
        if release_buffer > 0.0 and max_edge < (required_edge + release_buffer):
            return {
                "status": "monitor",
                "reason_code": "climate_release_not_confirmed",
                "reason": "글로벌 기후 시장은 공식 월간 발표가 덜 모여서 더 큰 edge가 필요합니다.",
                "signal": None,
                "confidence": confidence,
                "max_edge": round(max_edge, 4),
                "required_edge": round(required_edge + release_buffer, 4),
                "fair_yes_prob": round(estimated_yes_prob, 4),
                "fair_no_prob": round(estimated_no_prob, 4),
                "weather_type": weather_type or fair_value.market_type,
                "regime": regime,
                "details": fair_value.details,
            }
        if yes_edge < required_edge and no_edge < required_edge:
            return {
                "status": "monitor",
                "reason_code": "edge_below_required",
                "reason": "모델 우위는 있지만 요구 edge 기준을 아직 못 넘었습니다.",
                "signal": None,
                "confidence": confidence,
                "max_edge": round(max_edge, 4),
                "required_edge": round(required_edge, 4),
                "fair_yes_prob": round(estimated_yes_prob, 4),
                "fair_no_prob": round(estimated_no_prob, 4),
                "weather_type": weather_type or fair_value.market_type,
                "regime": regime,
                "details": fair_value.details,
            }
        if confidence < self.MIN_CONFIDENCE and max_edge < (required_edge + 0.03):
            return {
                "status": "monitor",
                "reason_code": "confidence_too_low",
                "reason": "edge는 보이지만 confidence가 낮아 아직 보류입니다.",
                "signal": None,
                "confidence": confidence,
                "max_edge": round(max_edge, 4),
                "required_edge": round(required_edge + 0.03, 4),
                "fair_yes_prob": round(estimated_yes_prob, 4),
                "fair_no_prob": round(estimated_no_prob, 4),
                "weather_type": weather_type or fair_value.market_type,
                "regime": regime,
                "details": fair_value.details,
            }

        buy_yes = yes_edge >= no_edge
        token_id = yes_token_id if buy_yes else no_token_id
        if token_id is None:
            token_id = no_token_id if buy_yes else yes_token_id
        if token_id is None:
            return {
                "status": "blocked",
                "reason_code": "missing_selected_token",
                "reason": "선택한 방향의 token_id를 찾지 못했습니다.",
                "signal": None,
                "confidence": confidence,
                "max_edge": round(max_edge, 4),
                "required_edge": round(required_edge, 4),
            }

        chosen_estimated_prob = estimated_yes_prob if buy_yes else estimated_no_prob
        chosen_market_price = yes_price if buy_yes else no_price
        chosen_edge = yes_edge if buy_yes else no_edge

        city = opportunity.metadata.get("city", "")
        setup_type = self._setup_type(buy_yes=buy_yes, yes_price=yes_price)
        chosen_confidence = max(confidence, self.MIN_CONFIDENCE if setup_type != "fair_value" else confidence)
        budget_cap_usd = self._budget_cap_usd(
            edge=chosen_edge,
            confidence=chosen_confidence,
            setup_type=setup_type,
            regime=regime,
        )
        management = self._management_profile(
            regime=regime,
            market_price=chosen_market_price,
            edge=chosen_edge,
            confidence=chosen_confidence,
            setup_type=setup_type,
        )
        manual_plan = self._build_manual_plan(
            question=opportunity.question,
            buy_yes=buy_yes,
            yes_price=yes_price,
            no_price=no_price,
            fair_yes_prob=estimated_yes_prob,
            fair_no_prob=estimated_no_prob,
            confidence=chosen_confidence,
            edge=chosen_edge,
            regime=regime,
            management=management,
        )

        signal = Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=chosen_estimated_prob,
            market_price=chosen_market_price,
            confidence=chosen_confidence,
            strategy_name=self.name,
            metadata={
                "edge": chosen_edge,
                "yes_edge": yes_edge,
                "no_edge": no_edge,
                "fair_yes_prob": estimated_yes_prob,
                "fair_no_prob": estimated_no_prob,
                "model": fair_value.model,
                "native_enabled": self._kernel_instance().native_enabled,
                "weather_type": weather_type or fair_value.market_type,
                "city": city,
                "question": opportunity.question,
                "side_selected": "yes" if buy_yes else "no",
                "station_id": fair_value.station_id,
                "regime": regime,
                "setup_type": setup_type,
                "budget_cap_usd": budget_cap_usd,
                "required_edge": required_edge,
                "release_buffer": release_buffer,
                "bet_status": "bettable",
                "bet_reason_code": "pass",
                "bet_reason": "공정확률 우위, confidence, release 조건을 통과했습니다.",
                "manual_plan": manual_plan,
                **management,
                **fair_value.details,
            },
        )
        return {
            "status": "bettable",
            "reason_code": "pass",
            "reason": "지금 진입 가능한 조건입니다.",
            "signal": signal,
            "confidence": chosen_confidence,
            "max_edge": round(max_edge, 4),
            "required_edge": round(required_edge + release_buffer, 4),
            "fair_yes_prob": round(estimated_yes_prob, 4),
            "fair_no_prob": round(estimated_no_prob, 4),
            "weather_type": weather_type or fair_value.market_type,
            "regime": regime,
            "details": fair_value.details,
        }

    def _estimate_weather_prob(self, opportunity: Opportunity) -> Optional[float]:
        fair_value = self._estimate_weather_fair_value(opportunity)
        if fair_value is None:
            return None
        return fair_value.fair_yes_prob

    def _estimate_weather_prob_and_confidence(self, opportunity: Opportunity) -> Optional[Tuple[float, float]]:
        fair_value = self._estimate_weather_fair_value(opportunity)
        if fair_value is None:
            return None
        return fair_value.fair_yes_prob, fair_value.confidence

    def _estimate_weather_fair_value(self, opportunity: Opportunity) -> Optional[WeatherFairValue]:
        noaa = self.get_data("noaa_weather") or self.get_data("noaa")
        engine = self._engine(noaa)
        spec = engine.parse_market(
            opportunity.question,
            description=str(opportunity.metadata.get("description", "")),
            end_date_iso=opportunity.metadata.get("end_date_iso"),
            resolution_source=opportunity.metadata.get("resolution_source"),
        )
        if spec is not None:
            fair_value = engine.fair_value(spec)
            if fair_value is not None:
                opportunity.metadata["city"] = spec.canonical_city or spec.city
                opportunity.metadata["weather_type"] = spec.market_type
                opportunity.metadata["station_id"] = spec.station_id
                opportunity.metadata["station_label"] = spec.station_label
                opportunity.metadata["weather_contract"] = spec.to_metadata()
                opportunity.metadata["resolution_source"] = spec.resolution_source
                opportunity.metadata["settlement_source"] = spec.settlement_source
                opportunity.metadata["settlement_location_id"] = spec.settlement_location_id
                return fair_value

        return None

    @staticmethod
    def _extract_temperature(text: str) -> Optional[float]:
        return extract_temperature(text)

    @staticmethod
    def _extract_target_date(text: str) -> Optional[date]:
        return extract_target_date(text)

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
        return select_periods_for_target(forecast, target_date, horizon_hours)

    @staticmethod
    def _extract_temperatures(periods: List[dict]) -> List[float]:
        return extract_temperatures(periods)

    @staticmethod
    def _extract_temperature_contract(text: str) -> Optional[Tuple[str, float, Optional[float]]]:
        return extract_temperature_contract(text)

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _temperature_contract_probability(self, mu: float, sigma: float, contract: Tuple[str, float, Optional[float]]) -> float:
        return temperature_contract_probability(mu, sigma, contract)

    @staticmethod
    def _extract_horizon_hours(text: str) -> int:
        return extract_horizon_hours(text)

    def _scan_score(self, yes_price: float, no_price: float, volume: float, spec=None) -> float:
        score = 0.0
        if yes_price <= self.LONGSHOT_YES_MAX:
            score += 0.45
        if yes_price >= self.FADE_YES_MIN:
            score += 0.35
        score += min(0.12, math.log10(max(10.0, volume + 10.0)) * 0.03)
        if spec is not None and getattr(spec, "target_date", None) is not None:
            days_out = (spec.target_date - datetime.utcnow().date()).days
            if days_out <= 0:
                score += 0.18
            elif days_out == 1:
                score += 0.12
            elif days_out <= 3:
                score += 0.06
        if spec is not None and getattr(spec, "station_id", None):
            score += 0.10
        if yes_price > 0.02 and no_price > 0.02:
            score += 0.05
        return score

    def _required_edge(self, yes_price: float, no_price: float, confidence: float, regime: str) -> float:
        required = 0.06 if regime == "local_hold" else self.MIN_EDGE
        if yes_price <= self.LONGSHOT_YES_MAX or no_price <= self.LONGSHOT_YES_MAX:
            required = min(required, 0.045 if regime == "local_hold" else 0.035)
        if yes_price >= self.FADE_YES_MIN:
            required = min(required, 0.05 if regime == "local_hold" else 0.04)
        if confidence < 0.55:
            required += 0.02
        return required

    def _release_buffer(self, fair_value: WeatherFairValue, regime: str) -> float:
        if regime != "climate_reprice":
            return 0.0
        details = fair_value.details if isinstance(fair_value.details, dict) else {}
        if bool(details.get("is_published")):
            return 0.0
        buffer = 0.0
        source_count = int(details.get("source_count") or 1)
        months_ahead = int(details.get("months_ahead") or 0)
        if source_count < 2:
            buffer += 0.03
        if months_ahead >= 2:
            buffer += min(0.04, 0.01 * months_ahead)
        return buffer

    def _market_regime(self, question: str, weather_type: str) -> str:
        text = str(question or "").lower()
        if any(pattern.search(text) for pattern in self.CLIMATE_REPRICE_PATTERNS):
            return "climate_reprice"
        if weather_type in self.HOLD_MARKET_TYPES:
            return "local_hold"
        return "weather_reprice"

    def _setup_type(self, buy_yes: bool, yes_price: float) -> str:
        if buy_yes and yes_price <= self.LONGSHOT_YES_MAX:
            return "longshot_yes"
        if (not buy_yes) and yes_price >= self.FADE_YES_MIN:
            return "fade_yes"
        return "fair_value"

    def _management_profile(
        self,
        *,
        regime: str,
        market_price: float,
        edge: float,
        confidence: float,
        setup_type: str,
    ) -> Dict[str, Any]:
        if regime == "local_hold":
            take_profit = min(0.995, max(0.97, market_price + max(0.12, edge * 1.20)))
            review_below = max(0.01, market_price - min(0.06, max(0.03, edge * 0.50)))
            return {
                "exit_style": "hold_to_resolution",
                "hold_to_expiry": True,
                "take_profit_partial_price": None,
                "take_profit_price": round(take_profit, 4),
                "review_below_price": round(review_below, 4),
                "edge_recheck_floor": 0.0,
                "position_note": "기본은 만기보유, 0.97+ 또는 모델 붕괴 시만 조기정리",
            }

        partial_take_profit = min(0.90, max(0.65, market_price + max(0.12, edge * 0.90)))
        final_take_profit = min(0.995, max(0.95, market_price + max(0.18, edge * 1.15)))
        review_below = max(0.01, market_price - min(0.08, max(0.04, edge * 0.65)))
        return {
            "exit_style": "scale_out_reprice",
            "hold_to_expiry": False,
            "take_profit_partial_price": round(partial_take_profit, 4),
            "take_profit_price": round(final_take_profit, 4),
            "review_below_price": round(review_below, 4),
            "edge_recheck_floor": 0.02,
            "position_note": "재평가형: 중간 익절 후 0.95+ 구간에서 대부분 정리",
        }

    def _budget_cap_usd(self, edge: float, confidence: float, setup_type: str, regime: str) -> float:
        budget = self.BASE_BET + (0.5 if regime == "climate_reprice" else 0.0)
        budget += min(3.0, max(0.0, edge) * 25.0)
        budget += max(0.0, confidence - 0.50) * 6.0
        if setup_type != "fair_value":
            budget += 1.0
        return max(1.5, min(self.MAX_BET, budget))

    def _build_manual_plan(
        self,
        *,
        question: str,
        buy_yes: bool,
        yes_price: float,
        no_price: float,
        fair_yes_prob: float,
        fair_no_prob: float,
        confidence: float,
        edge: float,
        regime: str,
        management: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_price = yes_price if buy_yes else no_price
        fair_price = fair_yes_prob if buy_yes else fair_no_prob
        outcome = "Yes" if buy_yes else "No"
        suggested_limit = min(0.99, current_price + min(0.02, max(0.01, edge / 4)))
        do_not_chase_above = min(0.99, current_price + min(0.04, max(0.015, edge / 3)))
        take_profit = float(management.get("take_profit_price", current_price))
        partial_take_profit = management.get("take_profit_partial_price")
        review_below = float(management.get("review_below_price", max(0.01, current_price - 0.03)))
        hold_to_expiry = bool(management.get("hold_to_expiry"))
        if hold_to_expiry:
            instruction = (
                f"Polymarket에서 {outcome}를 {round(suggested_limit, 4)} 이하 지정가로 매수. "
                f"기본은 정산까지 보유하고, 가격이 {round(take_profit, 4)} 이상이면 조기익절 검토. "
                f"가격이 {round(review_below, 4)} 이하로 밀리거나 공정확률 우위가 사라지면 재점검."
            )
        else:
            partial_text = f"{round(float(partial_take_profit), 4)}" if partial_take_profit is not None else "-"
            instruction = (
                f"Polymarket에서 {outcome}를 {round(suggested_limit, 4)} 이하 지정가로 매수. "
                f"{partial_text}에서 일부 익절, {round(take_profit, 4)} 이상이면 대부분 정리. "
                f"가격이 {round(review_below, 4)} 이하로 밀리면 바로 재평가."
            )
        return {
            "mode": "manual",
            "manual_only": False,
            "question": question,
            "action": f"buy_{str(outcome).lower()}",
            "polymarket_outcome": outcome,
            "regime": regime,
            "status": "enter_now",
            "enter_now": True,
            "current_yes_price": round(yes_price, 4),
            "current_no_price": round(no_price, 4),
            "fair_yes_price": round(fair_yes_prob, 4),
            "fair_no_price": round(fair_no_prob, 4),
            "current_price": round(current_price, 4),
            "fair_price": round(fair_price, 4),
            "suggested_limit_price": round(suggested_limit, 4),
            "do_not_chase_above_price": round(do_not_chase_above, 4),
            "take_profit_price": round(take_profit, 4),
            "take_profit_partial_price": partial_take_profit,
            "review_below_price": round(review_below, 4),
            "edge": round(edge, 4),
            "confidence": round(confidence, 4),
            "hold_to_expiry": hold_to_expiry,
            "instruction_kr": instruction,
        }

    def _get_yes_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        budget_cap_usd = float(signal.metadata.get("budget_cap_usd", self.BASE_BET))
        budget_cap_usd = max(1.0, min(self.MAX_BET, budget_cap_usd))
        capped_size = min(size, budget_cap_usd / signal.market_price) if signal.market_price > 0 else 0
        if capped_size <= 0:
            return None
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=capped_size,
            strategy_name=self.name,
            market_id=signal.market_id,
            position_metadata={
                "question": signal.metadata.get("question"),
                "city": signal.metadata.get("city"),
                "regime": signal.metadata.get("regime"),
                "setup_type": signal.metadata.get("setup_type"),
                "take_profit_price": signal.metadata.get("take_profit_price"),
                "take_profit_partial_price": signal.metadata.get("take_profit_partial_price"),
                "review_below_price": signal.metadata.get("review_below_price"),
                "hold_to_expiry": signal.metadata.get("hold_to_expiry"),
            },
        )

    def build_manual_plan(
        self,
        signal: Signal,
        client=None,
        size: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        base_plan = super().build_manual_plan(signal, client=client, size=size)
        if not isinstance(base_plan, dict):
            return None
        plan = dict(base_plan)
        if size is not None:
            plan["size"] = round(float(size), 4)
        if client is not None and signal.token_id:
            try:
                quote = client.quote_token(signal.token_id)
            except Exception:
                quote = None
            if isinstance(quote, dict):
                for key in ["best_bid", "best_ask", "midpoint", "spread"]:
                    value = quote.get(key)
                    if value is not None:
                        plan[key] = round(float(value), 4)
        return plan
