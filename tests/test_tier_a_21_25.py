import pytest
from core.models import Market, Opportunity
from strategies.tier_a.s21_text_video_delay import TextVideoDelay
from strategies.tier_a.s22_longshot_bias import LongshotBias
from strategies.tier_a.s23_correlated_lag import CorrelatedLag
from strategies.tier_a.s24_model_vs_market import ModelVsMarket
from strategies.tier_a.s25_liquidity_reward import LiquidityReward


# --- S21: Text-Video Delay Sports Trading ---

def test_s21_scan_finds_live_sports_markets():
    s = TextVideoDelay()
    markets = [
        Market(condition_id="0x1", question="Will Team Liquid win this live Dota match?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], volume=8000),
        Market(condition_id="0x2", question="Will crude oil prices rise?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], volume=5000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s21_analyze_placeholder_returns_none():
    s = TextVideoDelay()
    opp = Opportunity(market_id="0x1", question="Live NBA game?", market_price=0.55,
                      metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S22: Longshot Bias Exploitation ---

def test_s22_scan_finds_longshot_markets():
    s = LongshotBias()
    markets = [
        Market(condition_id="0x1", question="Will alien life be confirmed by June?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.08"},
                       {"token_id": "n1", "outcome": "No", "price": "0.92"}], volume=3000),
        Market(condition_id="0x2", question="Will BTC hit 200K?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"},
                       {"token_id": "n2", "outcome": "No", "price": "0.50"}], volume=5000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"
    assert opps[0].market_price == 0.08


def test_s22_analyze_generates_buy_no_signal():
    s = LongshotBias()
    opp = Opportunity(market_id="0x1", question="Longshot event?", market_price=0.10,
                      metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"},
                                            {"token_id": "n1", "outcome": "No"}]})
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"
    assert signal.market_price == 0.90
    assert signal.estimated_prob == 0.93


# --- S23: Correlated Asset Lag ---

def test_s23_scan_groups_same_category():
    s = CorrelatedLag()
    markets = [
        Market(condition_id="0x1", question="Fed raises rates?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.70"}],
               category="economics"),
        Market(condition_id="0x2", question="Mortgage rates rise?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}],
               category="economics"),
        Market(condition_id="0x3", question="Lakers win?",
               tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.55"}],
               category="sports"),
    ]
    opps = s.scan(markets)
    # Only the 2 economics markets form a group; sports is alone
    assert len(opps) == 2
    assert all(o.category == "economics" for o in opps)


def test_s23_analyze_placeholder_returns_none():
    s = CorrelatedLag()
    opp = Opportunity(market_id="0x1", question="Related?", market_price=0.50,
                      metadata={"tokens": [], "group_size": 3})
    assert s.analyze(opp) is None


# --- S24: Model vs Market Divergence ---

def test_s24_scan_finds_political_markets():
    s = ModelVsMarket()
    markets = [
        Market(condition_id="0x1", question="Will the Democrat win the Senate race?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.45"}], volume=20000),
        Market(condition_id="0x2", question="Will it rain tomorrow?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.30"}], volume=1000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s24_analyze_placeholder_returns_none():
    s = ModelVsMarket()
    opp = Opportunity(market_id="0x1", question="Election?", market_price=0.45,
                      metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S25: Liquidity Reward Optimization ---

def test_s25_scan_finds_low_liquidity_markets():
    s = LiquidityReward()
    markets = [
        Market(condition_id="0x1", question="New niche market?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}],
               liquidity=10000),
        Market(condition_id="0x2", question="Popular market?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}],
               liquidity=200000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s25_analyze_generates_bid_near_midpoint():
    s = LiquidityReward()
    opp = Opportunity(market_id="0x1", question="Niche?", market_price=0.50,
                      metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"},
                                            {"token_id": "n1", "outcome": "No"}],
                                "liquidity": 5000})
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.token_id == "y1"
    assert signal.side == "buy"
    assert signal.market_price == 0.48  # midpoint(0.50) - spread(0.02)
    assert signal.metadata["bid"] == 0.48
    assert signal.metadata["ask"] == 0.52
