import pytest
from core.models import Market, Opportunity
from data import DataRegistry
from data.base_rates import BaseRateProvider
from strategies.tier_s.s01_reversing_stupidity import ReversingStupidity
from strategies.tier_s.s02_weather_noaa import WeatherNOAA
from strategies.tier_s.s03_nothing_ever_happens import NothingEverHappens
from strategies.tier_s.s04_cross_platform_arb import CrossPlatformArb
from strategies.tier_s.s05_negrisk_rebalancing import NegRiskRebalancing


# S01 Tests
def test_s01_scan_finds_overheated():
    s = ReversingStupidity()
    markets = [Market(
        condition_id="0x1",
        question="Will Trump win 2028?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
            {"token_id": "n1", "outcome": "No", "price": "0.20"},
        ],
        volume=50000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s01_scan_ignores_normal():
    s = ReversingStupidity()
    markets = [Market(
        condition_id="0x1",
        question="Will inflation decrease?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}],
        volume=50000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 0


def test_s01_scan_ignores_substring_false_positive():
    s = ReversingStupidity()
    markets = [Market(
        condition_id="0x1",
        question="Will the Golden State Warriors win the 2026 NBA Finals?",
        description="Sports market about the Warriors winning the NBA Finals.",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.68"},
            {"token_id": "n1", "outcome": "No", "price": "0.32"},
        ],
        volume=50000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 0


def test_s01_scan_finds_live_style_trump_out_market():
    s = ReversingStupidity()
    markets = [Market(
        condition_id="0x1",
        question="Trump out as President before GTA VI?",
        description="This market resolves Yes if Donald Trump ceases to be the President of the U.S. before GTA VI releases.",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.53"},
            {"token_id": "n1", "outcome": "No", "price": "0.47"},
        ],
        volume=50000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s01_analyze_produces_signal():
    s = ReversingStupidity()
    opp = Opportunity(
        market_id="0x1",
        question="Will Trump win?",
        market_price=0.80,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ]
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"  # Buy NO
    assert signal.token_id == "n1"


def test_s01_manual_plan_includes_explicit_entry_levels():
    s = ReversingStupidity()
    opp = Opportunity(
        market_id="0x1",
        question="Will Trump win?",
        market_price=0.80,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ]
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    plan = signal.metadata["manual_plan"]
    assert plan["trigger_yes_price_gte"] >= 0.68
    assert plan["suggested_limit_no_price"] >= 0.20
    assert plan["do_not_chase_above_no_price"] >= plan["suggested_limit_no_price"]
    assert "지금" in plan["instruction_kr"] or "대기" in plan["instruction_kr"]


def test_s01_manual_plan_uses_live_quote_when_available():
    s = ReversingStupidity()
    opp = Opportunity(
        market_id="0x1",
        question="Will Trump win?",
        market_price=0.80,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ]
        },
    )
    signal = s.analyze(opp)
    assert signal is not None

    class StubClient:
        def quote_token(self, token_id):
            assert token_id == "n1"
            return {"best_bid": 0.205, "best_ask": 0.214, "midpoint": 0.2095, "spread": 0.009}

    plan = s.build_manual_plan(signal, client=StubClient(), size=125.0)
    assert plan is not None
    assert plan["quote_source"] == "clob_orderbook"
    assert plan["best_ask_no_price"] == pytest.approx(0.214, abs=0.001)
    assert plan["recommended_limit_no_price"] >= 0.214
    assert plan["size"] == pytest.approx(125.0, abs=0.001)


def test_s01_manual_plan_marks_skip_chase_when_live_ask_too_high():
    s = ReversingStupidity()
    opp = Opportunity(
        market_id="0x1",
        question="Will Trump win?",
        market_price=0.80,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ]
        },
    )
    signal = s.analyze(opp)
    assert signal is not None

    class StubClient:
        def quote_token(self, token_id):
            return {"best_bid": 0.23, "best_ask": 0.26, "midpoint": 0.245, "spread": 0.03}

    plan = s.build_manual_plan(signal, client=StubClient(), size=125.0)
    assert plan is not None
    assert plan["status"] == "skip_chase"
    assert "추격" in plan["instruction_kr"]


def test_s01_trump_out_market_uses_event_specific_prior_floor():
    s = ReversingStupidity()
    registry = DataRegistry()
    registry.register(BaseRateProvider())
    s.set_data_registry(registry)

    opp = Opportunity(
        market_id="0x1",
        question="Trump out as President before GTA VI?",
        market_price=0.525,
        category="politics",
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.525"},
                {"token_id": "n1", "outcome": "No", "price": "0.475"},
            ],
            "description": (
                "This market resolves Yes if Donald Trump ceases to be the President "
                "of the U.S. before GTA VI releases."
            ),
            "text_blob": (
                "trump out as president before gta vi "
                "donald trump ceases to be the president before gta vi releases"
            ),
            "end_date_iso": "2026-07-31T12:00:00Z",
        },
    )
    signal = s.analyze(opp)

    assert signal is not None
    assert signal.metadata["event_profile"]["name"] == "office_exit"
    assert signal.metadata["base_rate"] >= 0.22
    assert signal.metadata["manual_plan"]["trigger_yes_price_gte"] >= 0.38


def test_s01_ceasefire_market_requires_higher_trigger_than_generic_geopolitics():
    s = ReversingStupidity()
    registry = DataRegistry()
    registry.register(BaseRateProvider())
    s.set_data_registry(registry)

    opp = Opportunity(
        market_id="0x1",
        question="Russia-Ukraine Ceasefire before GTA VI?",
        market_price=0.58,
        category="geopolitical",
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.58"},
                {"token_id": "n1", "outcome": "No", "price": "0.42"},
            ],
            "description": (
                "This market resolves Yes if there is an official ceasefire agreement "
                "between Russia and Ukraine before GTA VI releases."
            ),
            "text_blob": (
                "russia-ukraine ceasefire before gta vi official ceasefire agreement "
                "between russia and ukraine before gta vi releases"
            ),
            "end_date_iso": "2026-07-31T12:00:00Z",
        },
    )
    signal = s.analyze(opp)

    assert signal is not None
    assert signal.metadata["event_profile"]["name"] == "ceasefire"
    assert signal.metadata["base_rate"] >= 0.24
    assert signal.metadata["manual_plan"]["trigger_yes_price_gte"] >= 0.42


def test_s01_invasion_market_uses_event_specific_trigger_floor():
    s = ReversingStupidity()
    registry = DataRegistry()
    registry.register(BaseRateProvider())
    s.set_data_registry(registry)

    opp = Opportunity(
        market_id="0x1",
        question="Will China invades Taiwan before GTA VI?",
        market_price=0.515,
        category="geopolitical",
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.515"},
                {"token_id": "n1", "outcome": "No", "price": "0.485"},
            ],
            "description": (
                "This market resolves Yes if China commences a military offensive "
                "intended to establish control over Taiwan before GTA VI releases."
            ),
            "text_blob": (
                "will china invades taiwan before gta vi "
                "china commences a military offensive intended to establish control over taiwan "
                "before gta vi releases"
            ),
            "end_date_iso": "2026-07-31T12:00:00Z",
        },
    )
    signal = s.analyze(opp)

    assert signal is not None
    assert signal.metadata["event_profile"]["name"] == "military_invasion"
    assert signal.metadata["base_rate"] >= 0.18
    assert signal.metadata["manual_plan"]["trigger_yes_price_gte"] >= 0.36


def test_s01_execute_is_blocked_by_default(monkeypatch):
    s = ReversingStupidity()
    opp = Opportunity(
        market_id="0x1",
        question="Will Trump win?",
        market_price=0.80,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ]
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    monkeypatch.delenv("S01_ENABLE_EXECUTION", raising=False)
    assert s.execute(signal, size=100.0, client=object()) is None


# S02 Tests
def test_s02_scan_finds_weather():
    s = WeatherNOAA()
    markets = [Market(
        condition_id="0x1",
        question="NYC high temperature above 80\u00b0F?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.10"}],
        volume=1000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s02_scan_ignores_non_weather():
    s = WeatherNOAA()
    markets = [Market(
        condition_id="0x1",
        question="Will BTC reach 100K?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.10"}],
        volume=1000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 0


# S03 Tests
def test_s03_scan_finds_dramatic():
    s = NothingEverHappens()
    markets = [Market(
        condition_id="0x1",
        question="Will Russia invade Poland?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.35"},
            {"token_id": "n1", "outcome": "No", "price": "0.65"},
        ],
        volume=10000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s03_analyze_bets_no():
    s = NothingEverHappens()
    opp = Opportunity(
        market_id="0x1",
        question="Will Russia invade?",
        market_price=0.35,
        metadata={"tokens": [{"token_id": "n1", "outcome": "No"}]},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"


# S04 Tests
def test_s04_scan():
    s = CrossPlatformArb()
    markets = [Market(
        condition_id="0x1",
        question="Fed rate cut?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}],
        volume=10000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s04_analyze_no_kalshi_returns_none():
    s = CrossPlatformArb()
    opp = Opportunity(
        market_id="0x1",
        question="Fed rate cut?",
        market_price=0.60,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}]},
    )
    signal = s.analyze(opp)
    assert signal is None  # No Kalshi data available


# S05 Tests
def test_s05_scan_finds_overpriced_multi():
    s = NegRiskRebalancing()
    markets = [Market(
        condition_id="0x1",
        question="Who wins?",
        tokens=[
            {"token_id": "t1", "outcome": "A", "price": "0.40"},
            {"token_id": "t2", "outcome": "B", "price": "0.35"},
            {"token_id": "t3", "outcome": "C", "price": "0.30"},
        ],
        volume=10000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].metadata["overprice"] == pytest.approx(0.05, abs=0.01)


def test_s05_scan_ignores_fair():
    s = NegRiskRebalancing()
    markets = [Market(
        condition_id="0x1",
        question="Who wins?",
        tokens=[
            {"token_id": "t1", "outcome": "A", "price": "0.50"},
            {"token_id": "t2", "outcome": "B", "price": "0.30"},
            {"token_id": "t3", "outcome": "C", "price": "0.20"},
        ],
        volume=10000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 0


def test_s05_analyze_overpriced():
    s = NegRiskRebalancing()
    opp = Opportunity(
        market_id="0x1",
        question="Who wins?",
        market_price=1.05,
        metadata={
            "tokens": [
                {"token_id": "t1", "outcome": "A", "price": "0.40"},
                {"token_id": "t2", "outcome": "B", "price": "0.35"},
                {"token_id": "t3", "outcome": "C", "price": "0.30"},
            ],
            "overprice": 0.05,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.token_id == "t1"  # Most overpriced
