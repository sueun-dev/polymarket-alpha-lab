# strategies/tier_s/s01_reversing_stupidity.py
"""
S01: Reversing Stupidity

Bet against emotionally overheated markets. After big events (elections,
major decisions), supporters flood markets with irrational bets.
Systematically take the opposite side.
"""
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class ReversingStupidity(BaseStrategy):
    name = "s01_reversing_stupidity"
    tier = "S"
    strategy_id = 1
    required_data = ["base_rates", "news", "ai"]

    SUBJECT_KEYWORDS = [
        "trump", "maga", "bitcoin", "btc", "china", "taiwan", "russia",
        "iran", "israel", "putin",
    ]
    EVENT_PATTERNS = [
        r"\bout as president\b",
        r"\bceasefire\b",
        r"\bceases?\s+to\s+be\s+the\s+president\b",
        r"\binvad(?:e|es|ed|ing|er|ers)\b",
        r"\bwar\b",
        r"\bcrash\b",
        r"\bcollapse\b",
        r"\bdefault\b",
        r"\bimpeach(?:ment|ed)?\b",
        r"\bresign(?:ation|ed|s)?\b",
        r"\bban(?:ned|s)?\b",
        r"\bconvict(?:ed|ion|s)?\b",
        r"\barrest(?:ed|s)?\b",
        r"\bprison\b",
        r"\bjail\b",
        r"\breturn\b",
        r"\bsecond coming\b",
        r"\bmoon\b",
        r"\bguaranteed\b",
        r"\binevitable\b",
        r"\b100%\b",
        r"\b\$?1m\b",
    ]
    ALLOWED_CATEGORIES = {
        "politics", "geopolitical", "crypto", "economics", "technology", "science", "unknown",
    }
    MIN_VOLUME = 10000
    MIN_YES_PRICE = 0.40
    MAX_YES_PRICE = 0.90
    OVERREACTION_THRESHOLD = 0.18
    CATEGORY_THRESHOLD_OVERRIDES = {
        "crypto": 0.12,
        "politics": 0.15,
        "geopolitical": 0.15,
        "economics": 0.15,
        "technology": 0.16,
        "science": 0.16,
        "unknown": 0.18,
    }
    EVENT_PRIOR_PROFILES = (
        {
            "name": "office_exit",
            "patterns": (
                r"\bout as president\b",
                r"\bceases?\s+to\s+be\s+the\s+president\b",
                r"\bresign(?:ation|ed|s)?\b",
                r"\bimpeach(?:ment|ed)?\b",
                r"\bremoved?\s+from\s+office\b",
            ),
            "min_yes_by_days": ((180, 0.22), (365, 0.28), (99999, 0.35)),
            "threshold": 0.16,
        },
        {
            "name": "ceasefire",
            "patterns": (
                r"\bceasefire\b",
                r"\btruce\b",
                r"\bpeace\s+deal\b",
                r"\bpeace\s+agreement\b",
            ),
            "min_yes_by_days": ((180, 0.24), (365, 0.30), (99999, 0.38)),
            "threshold": 0.18,
        },
        {
            "name": "military_invasion",
            "patterns": (
                r"\binvad(?:e|es|ed|ing|er|ers)\b",
                r"\bmilitary\s+offensive\b",
                r"\bwar\b",
            ),
            "min_yes_by_days": ((180, 0.18), (365, 0.22), (99999, 0.28)),
            "threshold": 0.18,
        },
        {
            "name": "criminal_penalty",
            "patterns": (
                r"\bconvict(?:ed|ion|s)?\b",
                r"\barrest(?:ed|s)?\b",
                r"\bprison\b",
                r"\bjail\b",
            ),
            "min_yes_by_days": ((180, 0.28), (365, 0.35), (99999, 0.45)),
            "threshold": 0.16,
        },
        {
            "name": "extreme_crypto_target",
            "patterns": (
                r"\bbitcoin\b.*\b(hit|reach)\b",
                r"\bbtc\b.*\b(hit|reach)\b",
                r"\b\$?1m\b",
                r"\bone\s+million\b",
                r"\bmoon\b",
            ),
            "min_yes_by_days": ((180, 0.24), (365, 0.32), (99999, 0.40)),
            "threshold": 0.14,
        },
    )
    VOLUME_SPIKE_MULTIPLIER = 3.0
    MANUAL_ONLY = True
    TAKE_PROFIT_CAPTURE = 0.65
    STOP_BUFFER = 0.05
    NOVELTY_ANCHOR_PATTERNS = ("before gta vi", "before grand theft auto vi")
    NOVELTY_ANCHOR_THRESHOLD_BUMP = 0.01

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find liquid, binary markets with strong overreaction signatures."""
        opportunities = []
        base_rates = self.get_data("base_rates")
        for m in markets:
            if len(m.tokens) < 2:
                continue

            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            if yes_price < self.MIN_YES_PRICE or yes_price > self.MAX_YES_PRICE:
                continue
            if m.volume <= self.MIN_VOLUME:
                continue

            category = self._infer_category(m, base_rates)
            if category not in self.ALLOWED_CATEGORIES:
                continue

            text = self._text_blob(m)
            event_score = self._event_score(text)
            if event_score <= 0:
                continue

            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=category,
                metadata={
                    "tokens": m.tokens,
                    "volume": m.volume,
                    "description": m.description,
                    "event_score": event_score,
                    "text_blob": text,
                    "end_date_iso": m.end_date_iso,
                    "slug": m.slug,
                },
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        yes_price = opportunity.market_price

        # Use category-specific base rate if available
        base_rates = self.get_data("base_rates")
        news = self.get_data("news")
        ai = self.get_data("ai")
        ai_judgment = None
        sentiment_data = None
        text_blob = str(opportunity.metadata.get("text_blob", opportunity.question))
        event_profile = self._match_event_profile(
            text_blob,
            str(opportunity.metadata.get("end_date_iso", "")).strip() or None,
        )

        if base_rates is not None:
            # Use category base rate for the "fair value" of dramatic events
            category = opportunity.category or "unknown"
            if category == "unknown" and hasattr(base_rates, "categorize_text"):
                category = base_rates.categorize_text(
                    opportunity.question,
                    str(opportunity.metadata.get("description", "")),
                )
            elif category == "unknown" and hasattr(base_rates, "categorize_question"):
                category = base_rates.categorize_question(opportunity.question)
            no_rate = base_rates.get_no_rate(category)
            base_rate = 1.0 - no_rate  # YES fair value
        else:
            base_rate = 0.50  # Original fallback

        if event_profile is not None:
            base_rate = max(base_rate, float(event_profile["min_yes_prob"]))

        # If news provider available, check for volume-driving sentiment
        if news is not None:
            sentiment_data = news.get_sentiment_for_market(opportunity.question)
            if sentiment_data and sentiment_data.get("avg_sentiment", 0) > 0.3:
                # Positive sentiment driving YES up -- even more likely overpriced
                base_rate = max(0.01, base_rate * 0.9)  # Reduce fair value further

        rule_base_rate = base_rate
        overreaction_threshold = self._overreaction_threshold(
            opportunity.category or "unknown",
            text_blob,
            event_profile=event_profile,
        )

        if ai is not None and hasattr(ai, "judge_overreaction"):
            article_titles = []
            if sentiment_data:
                article_titles = [
                    str(article.get("title", "")).strip()
                    for article in sentiment_data.get("articles", [])
                    if str(article.get("title", "")).strip()
                ][:3]

            ai_judgment = ai.judge_overreaction(
                question=opportunity.question,
                yes_price=yes_price,
                category=opportunity.category or "unknown",
                volume=float(opportunity.metadata.get("volume", 0.0)),
                description=str(opportunity.metadata.get("description", "")),
                rule_yes_prob=rule_base_rate,
                news_sentiment=(
                    float(sentiment_data.get("avg_sentiment"))
                    if sentiment_data and sentiment_data.get("avg_sentiment") is not None
                    else None
                ),
                article_titles=article_titles,
            )
            if ai_judgment is not None:
                if not ai_judgment.get("should_fade_yes", False):
                    return None
                blend_weight = float(ai_judgment.get("blend_weight", getattr(ai, "blend_weight", 0.65)))
                ai_fair_yes = float(ai_judgment.get("fair_yes_prob", rule_base_rate))
                base_rate = ((1.0 - blend_weight) * rule_base_rate) + (blend_weight * ai_fair_yes)

        if yes_price - base_rate < overreaction_threshold:
            return None

        # Bet NO (sell YES equivalent)
        no_token_id = self._get_no_token_id(opportunity)
        if not no_token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=no_token_id,
            side="buy",  # Buy NO
            estimated_prob=1 - base_rate,  # NO probability
            market_price=1 - yes_price,  # NO price
            confidence=float(ai_judgment.get("confidence", 0.7)) if ai_judgment else 0.7,
            strategy_name=self.name,
            metadata={
                "yes_price": yes_price,
                "no_price": 1 - yes_price,
                "base_rate": base_rate,
                "rule_base_rate": rule_base_rate,
                "overreaction_threshold": overreaction_threshold,
                "ai_judgment": ai_judgment,
                "event_profile": event_profile,
                "event_score": opportunity.metadata.get("event_score", 0),
                "manual_plan": self._build_manual_plan(
                    question=opportunity.question,
                    yes_price=yes_price,
                    fair_yes=base_rate,
                    confidence=float(ai_judgment.get("confidence", 0.7)) if ai_judgment else 0.7,
                    category=opportunity.category or "unknown",
                    threshold=overreaction_threshold,
                ),
            },
        )

    def _text_blob(self, market: Market) -> str:
        return " ".join(
            part.strip().lower()
            for part in [market.question, market.description]
            if str(part or "").strip()
        )

    def _contains_word(self, text: str, word: str) -> bool:
        return re.search(rf"\b{re.escape(word.lower())}\b", text) is not None

    def _event_score(self, text: str) -> int:
        score = 0
        for keyword in self.SUBJECT_KEYWORDS:
            if self._contains_word(text, keyword):
                score += 1
        for pattern in self.EVENT_PATTERNS:
            if re.search(pattern, text):
                score += 2
        return score

    def _infer_category(self, market: Market, base_rates) -> str:
        if market.category:
            return market.category
        if base_rates is not None and hasattr(base_rates, "categorize_text"):
            return base_rates.categorize_text(market.question, market.description)
        if base_rates is not None and hasattr(base_rates, "categorize_question"):
            return base_rates.categorize_question(market.question)
        return "unknown"

    def _overreaction_threshold(
        self,
        category: str,
        text: str,
        event_profile: Optional[Dict[str, Any]] = None,
    ) -> float:
        threshold = self.CATEGORY_THRESHOLD_OVERRIDES.get(category, self.OVERREACTION_THRESHOLD)
        if event_profile is not None:
            threshold = max(threshold, float(event_profile.get("threshold", threshold)))
        if self._is_novelty_anchor(text):
            threshold += self.NOVELTY_ANCHOR_THRESHOLD_BUMP
        return max(0.10, min(0.35, threshold))

    def _match_event_profile(self, text: str, end_date_iso: Optional[str]) -> Optional[Dict[str, Any]]:
        days_to_resolution = self._days_to_resolution(end_date_iso)
        for profile in self.EVENT_PRIOR_PROFILES:
            if any(re.search(pattern, text) for pattern in profile["patterns"]):
                return {
                    "name": profile["name"],
                    "min_yes_prob": self._select_yes_prob(profile["min_yes_by_days"], days_to_resolution),
                    "threshold": float(profile["threshold"]),
                    "days_to_resolution": days_to_resolution,
                }
        return None

    def _select_yes_prob(self, schedule: Any, days_to_resolution: Optional[int]) -> float:
        for max_days, yes_prob in schedule:
            if days_to_resolution is not None and days_to_resolution <= int(max_days):
                return float(yes_prob)
        return float(schedule[-1][1])

    def _days_to_resolution(self, end_date_iso: Optional[str]) -> Optional[int]:
        if not end_date_iso:
            return None
        try:
            normalized = end_date_iso.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = dt - datetime.now(timezone.utc)
            return max(0, int(delta.total_seconds() // 86400))
        except Exception:
            return None

    def _is_novelty_anchor(self, text: str) -> bool:
        return any(anchor in text for anchor in self.NOVELTY_ANCHOR_PATTERNS)

    def _build_manual_plan(
        self,
        *,
        question: str,
        yes_price: float,
        fair_yes: float,
        confidence: float,
        category: str,
        threshold: float,
    ) -> dict:
        no_price = 1 - yes_price
        fair_no = 1 - fair_yes
        edge = fair_no - no_price
        trigger_yes = min(0.99, fair_yes + threshold)
        trigger_no = max(0.01, 1 - trigger_yes)
        suggested_limit = min(0.99, no_price + min(0.02, max(0.01, edge / 4)))
        do_not_chase_above = min(0.99, no_price + min(0.03, max(0.015, edge / 3)))
        take_profit = min(0.99, no_price + max(0.04, edge * self.TAKE_PROFIT_CAPTURE))
        review_below = max(0.01, no_price - min(self.STOP_BUFFER, max(0.03, edge / 2)))
        status = "enter_now" if yes_price >= trigger_yes else "wait"

        return {
            "mode": "manual",
            "manual_only": True,
            "question": question,
            "category": category,
            "action": "buy_no",
            "polymarket_outcome": "No",
            "status": status,
            "enter_now": yes_price >= trigger_yes,
            "current_yes_price": round(yes_price, 4),
            "current_no_price": round(no_price, 4),
            "fair_yes_price": round(fair_yes, 4),
            "fair_no_price": round(fair_no, 4),
            "trigger_yes_price_gte": round(trigger_yes, 4),
            "trigger_no_price_lte": round(trigger_no, 4),
            "suggested_limit_no_price": round(suggested_limit, 4),
            "do_not_chase_above_no_price": round(do_not_chase_above, 4),
            "take_profit_no_price_gte": round(take_profit, 4),
            "review_if_no_price_lte": round(review_below, 4),
            "estimated_edge": round(edge, 4),
            "confidence": round(confidence, 4),
            "instruction_kr": (
                f"{'지금 진입' if status == 'enter_now' else '대기'}: "
                f"YES가 {round(trigger_yes, 4)} 이상이거나 NO가 {round(trigger_no, 4)} 이하일 때 "
                f"Polymarket에서 NO를 선택하고 {round(suggested_limit, 4)} 이하 지정가 매수. "
                f"NO가 {round(do_not_chase_above, 4)}를 넘으면 추격 금지."
            ),
        }

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
        quote: Optional[Dict[str, Any]] = None
        if client is not None and signal.token_id:
            try:
                quote = client.quote_token(signal.token_id)
            except Exception:
                quote = None

        current_no = float(plan.get("current_no_price", signal.market_price))
        trigger_yes = float(plan.get("trigger_yes_price_gte", 0.0))
        trigger_no = float(plan.get("trigger_no_price_lte", 0.0))
        do_not_chase = float(plan.get("do_not_chase_above_no_price", current_no))
        suggested_limit = float(plan.get("suggested_limit_no_price", current_no))
        best_bid = None
        best_ask = None
        midpoint = None
        spread = None

        if isinstance(quote, dict):
            best_bid = self._maybe_float(quote.get("best_bid"))
            best_ask = self._maybe_float(quote.get("best_ask"))
            midpoint = self._maybe_float(quote.get("midpoint"))
            spread = self._maybe_float(quote.get("spread"))

        reference_no = best_ask if best_ask is not None else current_no
        recommended_limit = min(do_not_chase, max(reference_no, suggested_limit))
        if reference_no > do_not_chase:
            status = "skip_chase"
        elif bool(plan.get("enter_now")):
            status = "enter_now"
        else:
            status = "wait"

        if status == "skip_chase":
            instruction_kr = (
                f"지금은 NO 최저호가가 {reference_no:.4f}라 상단 진입 한도 {do_not_chase:.4f}를 넘었습니다. "
                f"추격하지 말고 YES가 {trigger_yes:.4f} 이상으로 더 과열되거나 "
                f"NO가 {do_not_chase:.4f} 이하로 다시 내려올 때만 재확인하세요."
            )
        elif status == "enter_now":
            size_text = f"추천 계약 수량 {size:.4f} 기준, " if size is not None and size > 0 else ""
            instruction_kr = (
                f"지금 Polymarket에서 NO를 선택하고 {recommended_limit:.4f} 이하 지정가로 매수하세요. "
                f"{size_text}현재 NO 호가는 {reference_no:.4f}입니다. "
                f"NO가 {plan['take_profit_no_price_gte']:.4f} 이상이면 이익실현 검토, "
                f"{plan['review_if_no_price_lte']:.4f} 이하로 밀리면 재검토하세요."
            )
        else:
            instruction_kr = (
                f"아직 대기하세요. YES가 {trigger_yes:.4f} 이상이 되거나 "
                f"NO가 {trigger_no:.4f} 이하로 내려오면 "
                f"Polymarket에서 NO를 선택하고 {recommended_limit:.4f} 이하 지정가로 매수하세요. "
                f"NO가 {do_not_chase:.4f}를 넘으면 추격하지 마세요."
            )

        plan.update({
            "status": status,
            "quote_source": "clob_orderbook" if quote is not None else "market_snapshot",
            "best_bid_no_price": round(best_bid, 4) if best_bid is not None else None,
            "best_ask_no_price": round(best_ask, 4) if best_ask is not None else None,
            "midpoint_no_price": round(midpoint, 4) if midpoint is not None else None,
            "spread_no_price": round(spread, 4) if spread is not None else None,
            "reference_no_entry_price": round(reference_no, 4),
            "recommended_limit_no_price": round(recommended_limit, 4),
            "size": round(size, 4) if size is not None and size > 0 else None,
            "instruction_kr": instruction_kr,
        })
        return plan

    @staticmethod
    def _maybe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    def _get_no_token_id(self, opportunity: Opportunity) -> Optional[str]:
        tokens = opportunity.metadata.get("tokens", [])
        for t in tokens:
            if t.get("outcome", "").lower() == "no":
                return t.get("token_id", "")
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        allow_execution = os.environ.get("S01_ENABLE_EXECUTION", "").strip().lower() in {"1", "true", "yes", "on"}
        if self.MANUAL_ONLY and not allow_execution:
            return None
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=size,
            strategy_name=self.name,
        )
