"""Tests for data.ai_judge -- AIJudgeProvider."""
from __future__ import annotations

from unittest import mock

from data.ai_judge import AIJudgeProvider


def _mock_response(payload):
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


class TestAIJudgeProvider:
    def test_returns_none_without_api_keys(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            provider = AIJudgeProvider({"enabled": True})
            result = provider.judge_overreaction(
                question="Will Trump win 2028?",
                yes_price=0.80,
                category="politics",
                volume=50000,
            )
        assert result is None

    @mock.patch("data.ai_judge.httpx.post")
    def test_openai_single_provider(self, mock_post):
        mock_post.return_value = _mock_response({
            "output_text": (
                '{"should_fade_yes": true, "fair_yes_prob": 0.12, '
                '"confidence": 0.81, "crowd_overreaction_score": 0.92, '
                '"summary": "YES looks overheated."}'
            )
        })

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-openai-key"}, clear=True):
            provider = AIJudgeProvider({"providers": ["openai"]})
            result = provider.judge_overreaction(
                question="Will Trump win 2028?",
                yes_price=0.80,
                category="politics",
                volume=50000,
                rule_yes_prob=0.05,
            )

        assert result is not None
        assert result["should_fade_yes"] is True
        assert result["provider_count"] == 1
        assert result["providers_used"] == ["openai"]
        assert result["fair_yes_prob"] == 0.12
        assert result["confidence"] == 0.81
        mock_post.assert_called_once()

    @mock.patch("data.ai_judge.httpx.post")
    def test_dual_provider_consensus(self, mock_post):
        mock_post.side_effect = [
            _mock_response({
                "output_text": (
                    '{"should_fade_yes": true, "fair_yes_prob": 0.10, '
                    '"confidence": 0.80, "crowd_overreaction_score": 0.85, '
                    '"summary": "OpenAI says fade."}'
                )
            }),
            _mock_response({
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"should_fade_yes": true, "fair_yes_prob": 0.20, '
                            '"confidence": 0.70, "crowd_overreaction_score": 0.75, '
                            '"summary": "Claude agrees."}'
                        ),
                    }
                ]
            }),
        ]

        with mock.patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-openai-key",
                "ANTHROPIC_API_KEY": "test-anthropic-key",
            },
            clear=True,
        ):
            provider = AIJudgeProvider(
                {
                    "providers": ["openai", "anthropic"],
                    "require_consensus": True,
                }
            )
            result = provider.judge_overreaction(
                question="Will Trump win 2028?",
                yes_price=0.80,
                category="politics",
                volume=50000,
                rule_yes_prob=0.05,
                news_sentiment=0.4,
            )

        assert result is not None
        assert result["should_fade_yes"] is True
        assert result["provider_count"] == 2
        assert result["positive_votes"] == 2
        assert result["providers_used"] == ["openai", "anthropic"]
        assert 0.10 < result["fair_yes_prob"] < 0.20
        assert 0.70 < result["confidence"] < 0.81
