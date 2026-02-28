import pytest
from core.models import Market, Opportunity
from strategies.tier_c.s71_kaito_attention import KaitoAttention
from strategies.tier_c.s72_chainlink_oracle_timing import ChainlinkOracleTiming
from strategies.tier_c.s73_chinese_archetype import ChineseArchetype
from strategies.tier_c.s74_bot_psychology import BotPsychology
from strategies.tier_c.s75_reddit_contrarian import RedditContrarian
from strategies.tier_c.s76_conditional_prob import ConditionalProbChains
from strategies.tier_c.s77_historical_analogy import HistoricalAnalogy
from strategies.tier_c.s78_dune_sql_whale import DuneSqlWhaleTracking
from strategies.tier_c.s79_exit_timing import ExitTiming
from strategies.tier_c.s80_news_cycle import NewsCyclePositioning
from strategies.tier_c.s81_holiday_effect import HolidayEffect
from strategies.tier_c.s82_resolution_source_speed import ResolutionSourceSpeed
from strategies.tier_c.s83_multilang_sentiment import MultilangSentiment
from strategies.tier_c.s84_token_merger_arb import TokenMergerArb
from strategies.tier_c.s85_microcap_monopoly import MicrocapMonopoly


# --- S71: Kaito AI Attention Markets ---

def test_s71_scan_kaito_keywords():
    s = KaitoAttention()
    markets = [
        Market(condition_id="0x1", question="Will Kaito mindshare token hit $1?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40"}], active=True),
        Market(condition_id="0x2", question="AI attention index above 80?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.55"}], active=True),
        Market(condition_id="0x3", question="Will it rain tomorrow?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.30"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


# --- S72: Chainlink Oracle Update Timing ---

def test_s72_scan_oracle_keywords():
    s = ChainlinkOracleTiming()
    markets = [
        Market(condition_id="0x1", question="BTC price feed above 100K?", description="Uses Chainlink oracle", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], active=True),
        Market(condition_id="0x2", question="Will it snow?", description="Weather market", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.30"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S73: Chinese Three Trader Archetype ---

def test_s73_scan_all_active_with_volume():
    s = ChineseArchetype()
    markets = [
        Market(condition_id="0x1", question="Event A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], volume=5000, active=True),
        Market(condition_id="0x2", question="Event B?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], volume=2000, active=True),
        Market(condition_id="0x3", question="Event C?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.60"}], volume=50, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


# --- S74: Bot Behaviour Reverse-Engineering ---

def test_s74_scan_bot_trades():
    s = BotPsychology()
    markets = [
        Market(condition_id="0x1", question="Event A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50", "bot_trade_count": 20}], active=True),
        Market(condition_id="0x2", question="Event B?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40", "bot_trade_count": 3}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S75: Reddit Contrarian Sentiment ---

def test_s75_scan_reddit_keywords():
    s = RedditContrarian()
    markets = [
        Market(condition_id="0x1", question="Will Reddit IPO succeed?", description="Discussed on r/wallstreetbets", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.70"}], active=True),
        Market(condition_id="0x2", question="Will BTC hit 200K?", description="Crypto market speculation", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.10"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S76: Conditional Probability Chains ---

def test_s76_scan_conditional_keywords():
    s = ConditionalProbChains()
    markets = [
        Market(condition_id="0x1", question="If Democrats win House, will bill pass?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.45"}], active=True),
        Market(condition_id="0x2", question="Will BTC go up?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S77: Historical Analogy Matching ---

def test_s77_scan_political_keywords():
    s = HistoricalAnalogy()
    markets = [
        Market(condition_id="0x1", question="Will there be a government shutdown in 2026?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.35"}], active=True),
        Market(condition_id="0x2", question="Will it rain in NYC?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S78: Dune SQL Whale Tracking ---

def test_s78_scan_active_markets_with_volume():
    s = DuneSqlWhaleTracking()
    markets = [
        Market(condition_id="0x1", question="Event A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], volume=1000, active=True),
        Market(condition_id="0x2", question="Event B?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], volume=100, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S79: Optimal Exit Timing ---

def test_s79_scan_markets_with_positions():
    s = ExitTiming()
    markets = [
        Market(condition_id="0x1", question="Event A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.97", "has_position": True, "entry_price": 0.60, "position_size": 100, "position_side": "buy"}], active=True),
        Market(condition_id="0x2", question="Event B?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S80: News Cycle Positioning ---

def test_s80_scan_news_keywords():
    s = NewsCyclePositioning()
    markets = [
        Market(condition_id="0x1", question="Breaking: will CEO resign?", description="Latest news report", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.65"}], active=True),
        Market(condition_id="0x2", question="Will it rain?", description="Weather forecast", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.30"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S81: Holiday Trading Effects ---

def test_s81_scan_skips_non_holiday(monkeypatch):
    s = HolidayEffect()
    monkeypatch.setattr(s, "_near_holiday", lambda: False)
    markets = [
        Market(condition_id="0x1", question="Event A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 0


# --- S82: Resolution Source Speed Ranking ---

def test_s82_scan_fast_source_keywords():
    s = ResolutionSourceSpeed()
    markets = [
        Market(condition_id="0x1", question="Election result per AP call?", description="Resolved by Associated Press", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}], active=True),
        Market(condition_id="0x2", question="Will it rain?", description="No fast source", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S83: Multi-Language Sentiment Analysis ---

def test_s83_scan_international_keywords():
    s = MultilangSentiment()
    markets = [
        Market(condition_id="0x1", question="Will China GDP exceed 6%?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.45"}], active=True),
        Market(condition_id="0x2", question="Will Apple release a phone?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.90"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S84: Token Merger Arbitrage ---

def test_s84_scan_merger_keywords():
    s = TokenMergerArb()
    markets = [
        Market(condition_id="0x1", question="Market restructure after merge?", description="Tokens will consolidate", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x2", question="Will BTC moon?", description="Standard market", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.30"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S85: Monopolise Micro-Cap Markets ---

def test_s85_scan_low_liquidity():
    s = MicrocapMonopoly()
    markets = [
        Market(condition_id="0x1", question="Micro event?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], liquidity=80.0, active=True),
        Market(condition_id="0x2", question="Big event?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}], liquidity=50000.0, active=True),
        Market(condition_id="0x3", question="Another micro?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.40"}], liquidity=150.0, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x3" in ids
