import pytest
from core.models import Market, Opportunity
from strategies.tier_a.s26_ai_agent import AIAgentProbabilityTrading
from strategies.tier_a.s27_political_structure import StructuralPoliticalMispricing
from strategies.tier_a.s28_portfolio_agent import PortfolioBettingAgent
from strategies.tier_a.s29_earnings_streak import EarningsBeatStreak
from strategies.tier_a.s30_sportsbook_arb import CrossPlatformSportsbookArb


# --- S26: AI Agent Probability Trading ---

def test_s26_scan_all_active():
    s = AIAgentProbabilityTrading()
    markets = [
        Market(condition_id="0x1", question="Will it rain tomorrow?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40"}], active=True),
        Market(condition_id="0x2", question="Will BTC hit 200K?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.15"}], active=True),
        Market(condition_id="0x3", question="Inactive market", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.60"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    assert all(o.market_id in ("0x1", "0x2") for o in opps)


def test_s26_analyze_placeholder_returns_none():
    s = AIAgentProbabilityTrading()
    opp = Opportunity(market_id="0x1", question="Will it rain?", market_price=0.40, metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S27: Structural Political Mispricing ---

def test_s27_scan_political_keywords():
    s = StructuralPoliticalMispricing()
    markets = [
        Market(condition_id="0x1", question="Will Democrats win the Senate in 2026?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.45"}], active=True),
        Market(condition_id="0x2", question="Will BTC hit 100K?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x3", question="Governor race in Texas?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.55"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids  # "senate"
    assert "0x3" in ids  # "governor"


def test_s27_analyze_placeholder_returns_none():
    s = StructuralPoliticalMispricing()
    opp = Opportunity(market_id="0x1", question="Senate race?", market_price=0.45, metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S28: Portfolio Betting Agent ---

def test_s28_scan_volume_filter():
    s = PortfolioBettingAgent()
    markets = [
        Market(condition_id="0x1", question="High volume market", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], volume=10000, active=True),
        Market(condition_id="0x2", question="Low volume market", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}], volume=1000, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s28_analyze_near_center_returns_none():
    s = PortfolioBettingAgent()
    opp = Opportunity(
        market_id="0x1", question="Efficient market?", market_price=0.50,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}, {"token_id": "n1", "outcome": "No"}], "volume": 10000},
    )
    signal = s.analyze(opp)
    # Price at 0.50 -> distance_from_center = 0.0 < 0.10 -> None
    assert signal is None


# --- S29: Earnings Beat Streak ---

def test_s29_scan_earnings_keywords():
    s = EarningsBeatStreak()
    markets = [
        Market(condition_id="0x1", question="Will AAPL beat Q3 earnings?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], active=True),
        Market(condition_id="0x2", question="Will it rain tomorrow?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s29_analyze_with_streak():
    s = EarningsBeatStreak()
    opp = Opportunity(
        market_id="0x1", question="Will AAPL beat Q3 earnings?", market_price=0.60,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "streak_count": 12},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "y1"
    assert signal.estimated_prob == 0.75


# --- S30: Cross-Platform Sportsbook Arb ---

def test_s30_scan_sports_keywords():
    s = CrossPlatformSportsbookArb()
    markets = [
        Market(condition_id="0x1", question="Will the Lakers win the NBA championship?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}], active=True),
        Market(condition_id="0x2", question="Will the Fed raise rates?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s30_analyze_placeholder_returns_none():
    s = CrossPlatformSportsbookArb()
    opp = Opportunity(market_id="0x1", question="Lakers NBA?", market_price=0.30, metadata={"tokens": []})
    assert s.analyze(opp) is None
