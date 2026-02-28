import pytest
from datetime import datetime, timezone, timedelta

from core.models import Market, Opportunity
from strategies.tier_b.s41_resolution_timing import ResolutionTimingStrategy
from strategies.tier_b.s42_insider_pattern import InsiderPatternDetection
from strategies.tier_b.s43_time_weighted_momentum import TimeWeightedMomentumStrategy
from strategies.tier_b.s44_illiquid_market import IlliquidMarketStrategy
from strategies.tier_b.s45_twitter_sentiment_reversal import TwitterSentimentReversal
from strategies.tier_b.s46_portfolio_rebalance import PortfolioRebalanceStrategy
from strategies.tier_b.s47_parallel_market_monitor import ParallelMarketMonitor
from strategies.tier_b.s48_options_hedging import OptionsHedgingStrategy
from strategies.tier_b.s49_stablecoin_yield import StablecoinYieldStrategy
from strategies.tier_b.s50_multi_strategy_alloc import MultiStrategyAllocation


# --- S41: Resolution Timing ---

def test_s41_scan_near_resolution():
    s = ResolutionTimingStrategy()
    soon = (datetime.now(tz=timezone.utc) + timedelta(hours=24)).isoformat()
    far = (datetime.now(tz=timezone.utc) + timedelta(days=10)).isoformat()
    markets = [
        Market(condition_id="0x1", question="Resolves soon?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.90"}], end_date_iso=soon, active=True),
        Market(condition_id="0x2", question="Resolves far?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], end_date_iso=far, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s41_analyze_high_price_generates_signal():
    s = ResolutionTimingStrategy()
    opp = Opportunity(
        market_id="0x1", question="Resolves soon?", market_price=0.92,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}, {"token_id": "n1", "outcome": "No"}], "hours_remaining": 12},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "y1"


# --- S42: Insider Pattern Detection ---

def test_s42_scan_volume_spike():
    s = InsiderPatternDetection()
    markets = [
        Market(condition_id="0x1", question="Suspicious volume?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], volume=10000, liquidity=500, active=True),
        Market(condition_id="0x2", question="Normal volume?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], volume=1000, liquidity=500, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s42_analyze_placeholder_returns_none():
    s = InsiderPatternDetection()
    opp = Opportunity(market_id="0x1", question="Test?", market_price=0.60, metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S43: Time-Weighted Momentum ---

def test_s43_scan_all_active():
    s = TimeWeightedMomentumStrategy()
    markets = [
        Market(condition_id="0x1", question="Active 1?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], active=True),
        Market(condition_id="0x2", question="Inactive?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s43_analyze_upward_momentum():
    s = TimeWeightedMomentumStrategy()
    opp = Opportunity(
        market_id="0x1", question="Trending up?", market_price=0.60,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}, {"token_id": "n1", "outcome": "No"}], "price_7d_ago": 0.45},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.metadata["direction"] == "up"


# --- S44: Illiquid Market ---

def test_s44_scan_illiquid_high_volume():
    s = IlliquidMarketStrategy()
    markets = [
        Market(condition_id="0x1", question="Illiquid?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}], liquidity=200, volume=5000, active=True),
        Market(condition_id="0x2", question="Liquid?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], liquidity=10000, volume=5000, active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s44_analyze_underpriced_yes():
    s = IlliquidMarketStrategy()
    opp = Opportunity(
        market_id="0x1", question="Illiquid?", market_price=0.30,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}, {"token_id": "n1", "outcome": "No"}], "liquidity": 200, "volume": 5000},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "y1"


# --- S45: Twitter Sentiment Reversal ---

def test_s45_scan_all_active():
    s = TwitterSentimentReversal()
    markets = [
        Market(condition_id="0x1", question="Active?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x2", question="Inactive?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s45_analyze_placeholder_returns_none():
    s = TwitterSentimentReversal()
    opp = Opportunity(market_id="0x1", question="Test?", market_price=0.50, metadata={"tokens": []})
    assert s.analyze(opp) is None


# --- S46: Portfolio Rebalance ---

def test_s46_scan_all_active():
    s = PortfolioRebalanceStrategy()
    markets = [
        Market(condition_id="0x1", question="Active?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x2", question="Inactive?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1


def test_s46_analyze_underweight_buy():
    s = PortfolioRebalanceStrategy()
    opp = Opportunity(
        market_id="0x1", question="Underweight?", market_price=0.60,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "target_weight": 0.20, "current_weight": 0.10},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"


# --- S47: Parallel Market Monitor ---

def test_s47_scan_divergent_markets():
    s = ParallelMarketMonitor()
    markets = [
        Market(condition_id="0x1", question="Crypto A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.80"}], category="crypto", active=True),
        Market(condition_id="0x2", question="Crypto B?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], category="crypto", active=True),
    ]
    opps = s.scan(markets)
    # avg = 0.60, divergences: +0.20 and -0.20, both above 0.15 threshold
    assert len(opps) == 2


def test_s47_analyze_overpriced_buys_no():
    s = ParallelMarketMonitor()
    opp = Opportunity(
        market_id="0x1", question="Crypto A?", market_price=0.80, category="crypto",
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}, {"token_id": "n1", "outcome": "No"}], "group_avg_price": 0.60, "divergence": 0.20, "group_size": 3},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.token_id == "n1"


# --- S48: Options Hedging ---

def test_s48_scan_both_tokens():
    s = OptionsHedgingStrategy()
    markets = [
        Market(condition_id="0x1", question="Both tokens?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40"}, {"token_id": "n1", "outcome": "No", "price": "0.35"}], active=True),
        Market(condition_id="0x2", question="Only YES?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s48_analyze_underpriced_pair():
    s = OptionsHedgingStrategy()
    opp = Opportunity(
        market_id="0x1", question="Underpriced pair?", market_price=0.40,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}, {"token_id": "n1", "outcome": "No"}], "yes_price": 0.40, "no_price": 0.35, "volume": 1000},
    )
    signal = s.analyze(opp)
    # spread = 0.75, imbalance = 0.25 > 0.20 threshold
    assert signal is not None
    assert signal.side == "buy"


# --- S49: Stablecoin Yield ---

def test_s49_scan_high_prob():
    s = StablecoinYieldStrategy()
    markets = [
        Market(condition_id="0x1", question="High prob?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.95"}], active=True),
        Market(condition_id="0x2", question="Low prob?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s49_analyze_good_yield():
    s = StablecoinYieldStrategy()
    # Market at 0.92, resolving in 30 days -> annualized ~106 %, well above 5 % stablecoin
    end_date = (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat()
    opp = Opportunity(
        market_id="0x1", question="Yield?", market_price=0.92,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "end_date_iso": end_date},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.metadata["annualized_return"] > s.STABLECOIN_APY


# --- S50: Multi-Strategy Allocation ---

def test_s50_scan_all_active():
    s = MultiStrategyAllocation()
    markets = [
        Market(condition_id="0x1", question="Active?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x2", question="Inactive?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s50_analyze_with_scores():
    s = MultiStrategyAllocation()
    opp = Opportunity(
        market_id="0x1", question="Multi?", market_price=0.50,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "strategy_scores": {"s41": 0.8, "s43": 0.5, "s44": 0.3},
            "best_strategy": "s41",
            "best_signal": {"token_id": "y1", "side": "buy", "estimated_prob": 0.65},
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.metadata["best_strategy"] == "s41"
