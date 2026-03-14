from unittest.mock import patch

from core.models import Opportunity, Signal
from tools.weather_live_runner import collect_live_snapshot


class _StubClient:
    def quote_tokens(self, token_ids):
        return {
            "tok-bet": {"best_ask": 0.20, "best_bid": 0.19, "spread": 0.01, "ask_size": 100.0},
            "tok-mon": {"best_ask": 0.44, "best_bid": 0.40, "spread": 0.04, "ask_size": 50.0},
        }

    def get_price(self, token_id, side="buy"):
        return None


class _StubStrategy:
    def get_data(self, name):
        return None

    def scan_market_universe(self, markets, include_low_score=False):
        return list(markets)

    def evaluate_opportunity(self, opportunity):
        if opportunity.market_id == "bet":
            return {
                "status": "bettable",
                "reason_code": "pass",
                "reason": "ok",
                "confidence": 0.8,
                "max_edge": 0.35,
                "required_edge": 0.05,
                "signal": Signal(
                    market_id="bet",
                    token_id="tok-bet",
                    side="buy",
                    estimated_prob=0.65,
                    market_price=0.18,
                    confidence=0.8,
                    strategy_name="s02_weather_noaa",
                    metadata={"city": "chicago", "setup_type": "fair_value", "regime": "local_hold"},
                ),
            }
        if opportunity.market_id == "mon":
            return {
                "status": "monitor",
                "reason_code": "edge_below_required",
                "reason": "wait",
                "confidence": 0.62,
                "max_edge": 0.03,
                "required_edge": 0.05,
                "signal": None,
            }
        return {
            "status": "blocked",
            "reason_code": "no_fair_value",
            "reason": "blocked",
            "confidence": 0.0,
            "max_edge": None,
            "required_edge": None,
            "signal": None,
        }


def _opp(market_id: str, question: str) -> Opportunity:
    return Opportunity(
        market_id=market_id,
        question=question,
        market_price=0.2,
        category="weather",
        metadata={"candidate_score": 0.2},
    )


def test_collect_live_snapshot_surfaces_bettable_monitor_and_blocked():
    client = _StubClient()
    strategy = _StubStrategy()
    markets = [
        _opp("bet", "Will Chicago high temperature exceed 80 degrees fahrenheit on March 12?"),
        _opp("mon", "Will Chicago high temperature exceed 81 degrees fahrenheit on March 12?"),
        _opp("blk", "Will Chicago high temperature exceed 82 degrees fahrenheit on March 12?"),
    ]
    with patch("tools.weather_live_runner.load_markets_from_catalog_rows", return_value=markets):
        snapshot = collect_live_snapshot(
            client=client,
            strategy=strategy,
            max_markets=10,
            page_size=10,
            min_edge=0.05,
            min_confidence=0.5,
            catalog_rows=[{"condition_id": "bet"}, {"condition_id": "mon"}, {"condition_id": "blk"}],
            workers=1,
        )
    assert len(snapshot["ranked"]) == 1
    assert snapshot["ranked"][0]["market_id"] == "bet"
    assert len(snapshot["monitoring"]) == 1
    assert snapshot["monitoring"][0]["market_id"] == "mon"
    assert snapshot["monitoring"][0]["reason_code"] == "edge_below_required"
    assert len(snapshot["blocked"]) == 1
    assert snapshot["blocked"][0]["market_id"] == "blk"
    assert snapshot["blocked"][0]["reason_code"] == "no_fair_value"
