import pytest
from core.models import Market, Opportunity
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
