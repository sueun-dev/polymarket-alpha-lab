import pytest
from datetime import datetime, timedelta, timezone
from core.models import Market, Opportunity
from strategies.tier_a.s16_primary_source import PrimarySourceMonitoring
from strategies.tier_a.s17_whale_basket import WhaleBasketCopyTrading
from strategies.tier_a.s18_market_making import AutomatedMarketMaking
from strategies.tier_a.s19_kelly_framework import KellySizingFramework
from strategies.tier_a.s20_event_catalyst import EventCatalystPrePositioning


# S16 Tests
def test_s16_scan_finds_resolution_source():
    s = PrimarySourceMonitoring()
    markets = [Market(
        condition_id="0x1",
        question="Will the FDA approve drug X?",
        description="Resolves according to official FDA announcement.",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}],
        volume=5000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s16_scan_ignores_no_source():
    s = PrimarySourceMonitoring()
    markets = [Market(
        condition_id="0x1",
        question="Will it rain tomorrow?",
        description="Fun weather market.",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}],
        volume=5000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 0


# S17 Tests
def test_s17_scan_high_volume():
    s = WhaleBasketCopyTrading()
    markets = [Market(
        condition_id="0x1",
        question="Will BTC hit 200K?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}],
        volume=50000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s17_scan_ignores_low_volume():
    s = WhaleBasketCopyTrading()
    markets = [Market(
        condition_id="0x1",
        question="Will BTC hit 200K?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}],
        volume=500,
    )]
    opps = s.scan(markets)
    assert len(opps) == 0


# S18 Tests
def test_s18_scan_medium_liquidity():
    s = AutomatedMarketMaking()
    markets = [Market(
        condition_id="0x1",
        question="Will event X happen?",
        tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}],
        liquidity=5000,
        volume=10000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s18_analyze_produces_spread():
    s = AutomatedMarketMaking()
    opp = Opportunity(
        market_id="0x1",
        question="Will event X happen?",
        market_price=0.50,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}]},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.metadata["two_sided"] is True
    assert signal.metadata["bid_price"] < signal.metadata["ask_price"]
    assert signal.metadata["bid_price"] == pytest.approx(0.48, abs=0.01)
    assert signal.metadata["ask_price"] == pytest.approx(0.52, abs=0.01)


# S19 Tests
def test_s19_scan_passes_all_active():
    s = KellySizingFramework()
    markets = [
        Market(condition_id="0x1", question="Q1?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}]),
        Market(condition_id="0x2", question="Q2?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.70"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s19_analyze_with_edge():
    s = KellySizingFramework(kelly_fraction=0.5)
    opp = Opportunity(
        market_id="0x1",
        question="Q1?",
        market_price=0.40,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "estimated_prob": 0.60,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.estimated_prob == 0.60
    assert signal.metadata["kelly_fraction"] > 0
    assert signal.metadata["kelly_mode"] == "half"


# S20 Tests
def test_s20_scan_finds_upcoming_catalyst():
    s = EventCatalystPrePositioning()
    # Use midnight + 5 days to guarantee .days == 5
    now = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = (now + timedelta(days=5, hours=12)).isoformat()
    markets = [Market(
        condition_id="0x1",
        question="Will the Fed raise rates?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.55"},
            {"token_id": "n1", "outcome": "No", "price": "0.45"},
        ],
        end_date_iso=end_date,
        volume=10000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert 4 <= opps[0].metadata["days_until"] <= 5


def test_s20_analyze_inefficient_market():
    s = EventCatalystPrePositioning()
    opp = Opportunity(
        market_id="0x1",
        question="Will FOMC cut rates?",
        market_price=0.55,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes"},
                {"token_id": "n1", "outcome": "No"},
            ],
            "days_until": 5,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.strategy_name == "s20_event_catalyst"
    assert signal.estimated_prob > opp.market_price
