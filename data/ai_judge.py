"""Optional LLM-based sanity checks for strategy decisions."""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from data.base_provider import BaseDataProvider


class AIJudgeProvider(BaseDataProvider):
    """Runs optional OpenAI/Anthropic market sanity checks.

    The provider is designed as a thin, optional layer:
    - If no API keys are configured, it silently returns ``None``.
    - If one provider is configured, it uses that provider.
    - If both are configured, it aggregates both judgments.
    """

    name = "ai"

    DEFAULT_OPENAI_MODEL = "gpt-5.4"
    DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

    SYSTEM_PROMPT = (
        "You are an adversarial prediction-market risk judge. "
        "Your job is to decide whether the YES side of a market is emotionally "
        "overheated and should be faded contrarianly. "
        "Use only the provided context. Do not invent facts. "
        "Return JSON only with these keys: "
        "should_fade_yes (boolean), fair_yes_prob (number 0..1), "
        "confidence (number 0..1), crowd_overreaction_score (number 0..1), "
        "summary (short string)."
    )

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        super().__init__()
        cfg = config or {}

        self.enabled = _env_bool("AI_JUDGE_ENABLED", cfg.get("enabled", True))
        self.providers = _normalize_providers(
            _env_csv("AI_JUDGE_PROVIDERS", cfg.get("providers", ["openai", "anthropic"]))
        )
        if not self.providers:
            self.providers = ["openai", "anthropic"]

        self.require_consensus = _env_bool(
            "AI_JUDGE_REQUIRE_CONSENSUS",
            cfg.get("require_consensus", False),
        )
        self.min_confidence = _clamp(
            _env_float("AI_JUDGE_MIN_CONFIDENCE", cfg.get("min_confidence", 0.65)),
            0.0,
            1.0,
        )
        self.blend_weight = _clamp(
            _env_float("AI_JUDGE_BLEND_WEIGHT", cfg.get("blend_weight", 0.65)),
            0.0,
            1.0,
        )
        self.timeout_seconds = max(
            1.0,
            _env_float("AI_JUDGE_TIMEOUT_SECONDS", cfg.get("timeout_seconds", 20.0)),
        )
        self.max_output_tokens = max(
            128,
            _env_int("AI_JUDGE_MAX_OUTPUT_TOKENS", cfg.get("max_output_tokens", 350)),
        )
        self.cache_ttl_seconds = max(
            0,
            _env_int("AI_JUDGE_CACHE_TTL_SECONDS", cfg.get("cache_ttl_seconds", 300)),
        )

        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = (
            os.environ.get("OPENAI_JUDGE_MODEL")
            or cfg.get("openai_model")
            or self.DEFAULT_OPENAI_MODEL
        )
        self.openai_reasoning_effort = (
            os.environ.get("OPENAI_JUDGE_REASONING_EFFORT")
            or str(cfg.get("openai_reasoning_effort", "medium"))
        )

        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.anthropic_model = (
            os.environ.get("ANTHROPIC_JUDGE_MODEL")
            or cfg.get("anthropic_model")
            or self.DEFAULT_ANTHROPIC_MODEL
        )
        self.anthropic_version = (
            os.environ.get("ANTHROPIC_API_VERSION")
            or str(cfg.get("anthropic_version", "2023-06-01"))
        )

    def fetch(self, **kwargs: Any) -> Any:
        return self.judge_overreaction(**kwargs)

    def judge_overreaction(
        self,
        *,
        question: str,
        yes_price: float,
        category: str = "",
        volume: float = 0.0,
        description: str = "",
        rule_yes_prob: Optional[float] = None,
        news_sentiment: Optional[float] = None,
        article_titles: Optional[List[str]] = None,
    ) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        available = self._available_providers()
        if not available:
            return None

        context = {
            "question": question,
            "yes_price": round(_clamp(float(yes_price), 0.0, 1.0), 4),
            "category": category or "unknown",
            "volume": round(float(volume or 0.0), 2),
            "description": description or "",
            "rule_yes_prob": None if rule_yes_prob is None else round(_clamp(float(rule_yes_prob), 0.0, 1.0), 4),
            "news_sentiment": None if news_sentiment is None else round(_clamp(float(news_sentiment), -1.0, 1.0), 4),
            "article_titles": (article_titles or [])[:3],
        }
        cache_key = f"judge:{json.dumps(context, sort_keys=True)}:{','.join(available)}"
        cached = self.get_cached(cache_key, ttl=float(self.cache_ttl_seconds))
        if cached is not None:
            return cached  # type: ignore[return-value]

        prompt = self._build_prompt(context)
        judgments: List[dict[str, Any]] = []

        for provider_name in available:
            try:
                if provider_name == "openai":
                    judgment = self._judge_with_openai(prompt)
                elif provider_name == "anthropic":
                    judgment = self._judge_with_anthropic(prompt)
                else:
                    judgment = None
            except Exception:
                self.logger.warning("AI judge request failed for provider=%s", provider_name, exc_info=True)
                judgment = None

            if judgment is not None:
                judgments.append(judgment)

        if not judgments:
            return None

        aggregate = self._aggregate_judgments(judgments)
        self.set_cached(cache_key, aggregate)
        return aggregate

    def _available_providers(self) -> List[str]:
        names: List[str] = []
        if "openai" in self.providers and self.openai_api_key:
            names.append("openai")
        if "anthropic" in self.providers and self.anthropic_api_key:
            names.append("anthropic")
        return names

    def _build_prompt(self, context: dict[str, Any]) -> str:
        return (
            "Judge this market for contrarian fade-the-YES suitability.\n"
            "Focus on emotional overreaction, herd behavior, weak base-rate support, "
            "and whether the current YES price looks too high.\n"
            "If context is insufficient, lower confidence instead of guessing.\n\n"
            f"{json.dumps(context, ensure_ascii=True, sort_keys=True)}"
        )

    def _judge_with_openai(self, prompt: str) -> Optional[dict[str, Any]]:
        resp = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.openai_model,
                "instructions": self.SYSTEM_PROMPT,
                "input": prompt,
                "reasoning": {"effort": self.openai_reasoning_effort},
                "max_output_tokens": self.max_output_tokens,
            },
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        payload = resp.json()
        text = _extract_openai_text(payload)
        if not text:
            return None
        parsed = _extract_json_payload(text)
        return self._normalize_judgment("openai", parsed)

    def _judge_with_anthropic(self, prompt: str) -> Optional[dict[str, Any]]:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": str(self.anthropic_api_key),
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            },
            json={
                "model": self.anthropic_model,
                "system": self.SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_output_tokens,
            },
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        payload = resp.json()
        text = _extract_anthropic_text(payload)
        if not text:
            return None
        parsed = _extract_json_payload(text)
        return self._normalize_judgment("anthropic", parsed)

    def _normalize_judgment(
        self,
        provider_name: str,
        parsed: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        if not isinstance(parsed, dict):
            return None

        fair_yes_prob = _as_float(parsed.get("fair_yes_prob"))
        confidence = _as_float(parsed.get("confidence"))
        overreaction = _as_float(parsed.get("crowd_overreaction_score"))
        should_fade_yes = _as_bool(parsed.get("should_fade_yes"))
        summary = str(parsed.get("summary", "")).strip()

        if fair_yes_prob is None or confidence is None or should_fade_yes is None:
            return None

        return {
            "provider": provider_name,
            "model": self.openai_model if provider_name == "openai" else self.anthropic_model,
            "should_fade_yes": should_fade_yes,
            "fair_yes_prob": _clamp(fair_yes_prob, 0.0, 1.0),
            "confidence": _clamp(confidence, 0.0, 1.0),
            "crowd_overreaction_score": 0.0 if overreaction is None else _clamp(overreaction, 0.0, 1.0),
            "summary": summary[:240],
        }

    def _aggregate_judgments(self, judgments: List[dict[str, Any]]) -> dict[str, Any]:
        weights = [max(0.05, float(item["confidence"])) for item in judgments]
        weight_total = sum(weights) or 1.0
        fair_yes_prob = sum(
            float(item["fair_yes_prob"]) * weight
            for item, weight in zip(judgments, weights)
        ) / weight_total
        confidence = sum(float(item["confidence"]) for item in judgments) / len(judgments)
        overreaction = sum(float(item["crowd_overreaction_score"]) for item in judgments) / len(judgments)

        positive_votes = sum(1 for item in judgments if item["should_fade_yes"])
        majority = positive_votes >= math.ceil(len(judgments) / 2)
        unanimous = positive_votes == len(judgments)
        should_fade_yes = unanimous if (self.require_consensus and len(judgments) > 1) else majority
        actionable = should_fade_yes and confidence >= self.min_confidence

        return {
            "should_fade_yes": actionable,
            "fair_yes_prob": round(_clamp(fair_yes_prob, 0.0, 1.0), 4),
            "confidence": round(_clamp(confidence, 0.0, 1.0), 4),
            "crowd_overreaction_score": round(_clamp(overreaction, 0.0, 1.0), 4),
            "providers_used": [str(item["provider"]) for item in judgments],
            "models_used": [str(item["model"]) for item in judgments],
            "provider_count": len(judgments),
            "positive_votes": positive_votes,
            "require_consensus": self.require_consensus,
            "blend_weight": self.blend_weight,
            "summaries": [item["summary"] for item in judgments if item["summary"]],
        }


def _extract_openai_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    chunks: List[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _extract_anthropic_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""

    chunks: List[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _extract_json_payload(text: str) -> Optional[dict[str, Any]]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", stripped)
        stripped = re.sub(r"\n?```$", "", stripped)

    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_providers(values: List[str]) -> List[str]:
    normalized: List[str] = []
    for value in values:
        item = str(value).strip().lower()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _env_csv(name: str, default: Any) -> List[str]:
    raw = os.environ.get(name)
    if raw is None:
        if isinstance(default, list):
            return [str(item) for item in default]
        if isinstance(default, str):
            raw = default
        else:
            return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
