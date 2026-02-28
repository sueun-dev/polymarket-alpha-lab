import pytest
from unittest.mock import patch
from core.models import Market, Opportunity
from strategies.tier_b.s51_weather_microbet import WeatherMicroBet
from strategies.tier_b.s52_ensemble_weather import EnsembleWeather
from strategies.tier_b.s53_onchain_orderflow import OnchainOrderflow
from strategies.tier_b.s54_papal_anti_favorite import PapalAntiFavorite
from strategies.tier_b.s55_mention_market_no_bias import MentionMarketNoBias
from strategies.tier_b.s56_calendar_spread import CalendarSpread
from strategies.tier_b.s57_twitter_flow_fading import TwitterFlowFading
from strategies.tier_b.s58_sports_text_video import SportsTextVideo
from strategies.tier_b.s59_weekend_liquidity import WeekendLiquidity
from strategies.tier_b.s60_hedged_airdrop import HedgedAirdrop


# --- S51: Automated Weather Micro-Bets ---

def test_s51_scan_finds_cheap_weather_markets():
    s = WeatherMicroBet()
    markets = [
        Market(condition_id="0x1", question="Will temperature in New York exceed 90F?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.10"}], volume=2000),
        Market(condition_id="0x2", question="Will BTC hit 100K?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.08"}], volume=5000),
        Market(condition_id="0x3", question="Will it rain in Miami tomorrow?",
               tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.50"}], volume=3000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"
    assert opps[0].metadata["city"] == "new york"


# --- S52: Ensemble Weather Forecast Model ---

def test_s52_scan_finds_weather_markets():
    s = EnsembleWeather()
    markets = [
        Market(condition_id="0x1", question="Will it snow in Denver tomorrow?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"},
                       {"token_id": "n1", "outcome": "No", "price": "0.70"}], volume=2000),
        Market(condition_id="0x2", question="Will the election be contested?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.20"}], volume=5000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S53: On-Chain Order Flow Analysis ---

def test_s53_scan_filters_low_volume():
    s = OnchainOrderflow()
    markets = [
        Market(condition_id="0x1", question="Will BTC hit 100K?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40"}], volume=10000),
        Market(condition_id="0x2", question="Obscure market?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], volume=100),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S54: Anti-Favorite for Multi-Candidate Markets ---

def test_s54_scan_finds_multi_candidate_markets():
    s = PapalAntiFavorite()
    markets = [
        Market(condition_id="0x1", question="Who will be the next Pope?",
               tokens=[
                   {"token_id": "c1", "outcome": "Cardinal A", "price": "0.25"},
                   {"token_id": "c2", "outcome": "Cardinal B", "price": "0.20"},
                   {"token_id": "c3", "outcome": "Cardinal C", "price": "0.15"},
                   {"token_id": "c4", "outcome": "Cardinal D", "price": "0.10"},
               ], volume=50000),
        Market(condition_id="0x2", question="Will it rain tomorrow?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"},
                       {"token_id": "n1", "outcome": "No", "price": "0.40"}], volume=1000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"
    assert opps[0].metadata["combined_price"] == 0.60


# --- S55: "Will X Mention Y" Markets NO Bias ---

def test_s55_scan_finds_mention_markets():
    s = MentionMarketNoBias()
    markets = [
        Market(condition_id="0x1", question="Will Biden mention China in his speech?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"},
                       {"token_id": "n1", "outcome": "No", "price": "0.70"}], volume=3000),
        Market(condition_id="0x2", question="Will BTC hit 200K?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.10"}], volume=5000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S56: Calendar Spread Theta Harvesting ---

def test_s56_scan_finds_calendar_spread_pairs():
    s = CalendarSpread()
    markets = [
        Market(condition_id="0x1", question="Will BTC hit 100K by March?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40"}],
               end_date_iso="2026-03-31T00:00:00Z", volume=10000),
        Market(condition_id="0x2", question="Will BTC hit 100K by June?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.55"}],
               end_date_iso="2026-06-30T00:00:00Z", volume=8000),
        Market(condition_id="0x3", question="Will it rain tomorrow?",
               tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.30"}],
               end_date_iso="2026-03-01T00:00:00Z", volume=1000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].metadata["price_spread"] == pytest.approx(0.15)
    assert opps[0].metadata["days_apart"] == 91


# --- S57: Fade Twitter/X Flow Signals ---

def test_s57_analyze_placeholder_returns_none():
    s = TwitterFlowFading()
    opp = Opportunity(market_id="0x1", question="Will X happen?", market_price=0.50,
                      metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S58: Sports Text-Before-Video Trading ---

def test_s58_scan_finds_sports_markets():
    s = SportsTextVideo()
    markets = [
        Market(condition_id="0x1", question="Will the Lakers win this NBA game?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}], volume=15000),
        Market(condition_id="0x2", question="Will Congress pass the bill?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], volume=8000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S59: Weekend Liquidity Drop Exploitation ---

def test_s59_scan_only_runs_on_weekends():
    s = WeekendLiquidity()
    markets = [
        Market(condition_id="0x1", question="Any market?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], volume=5000),
    ]
    # Mock weekday -- should return no opportunities
    with patch.object(s, '_is_weekend', return_value=False):
        opps = s.scan(markets)
        assert len(opps) == 0
    # Mock weekend -- should return opportunities
    with patch.object(s, '_is_weekend', return_value=True):
        opps = s.scan(markets)
        assert len(opps) == 1
        assert opps[0].market_id == "0x1"


# --- S60: Hedged Airdrop Farming ---

def test_s60_scan_finds_liquid_hedgeable_markets():
    s = HedgedAirdrop()
    markets = [
        Market(condition_id="0x1", question="Will event X happen?",
               tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"},
                       {"token_id": "n1", "outcome": "No", "price": "0.51"}],
               liquidity=20000, volume=50000),
        Market(condition_id="0x2", question="Illiquid market?",
               tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"},
                       {"token_id": "n2", "outcome": "No", "price": "0.55"}],
               liquidity=500, volume=200),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"
    assert opps[0].metadata["spread"] == pytest.approx(0.01)
