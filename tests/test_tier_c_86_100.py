import pytest
from core.models import Market, Opportunity
from strategies.tier_c.s86_correlation_matrix import CorrelationMatrix
from strategies.tier_c.s87_ml_features import MLFeatureEngineering
from strategies.tier_c.s88_social_graph import SocialGraphAnalysis
from strategies.tier_c.s89_gas_optimization import GasOptimization
from strategies.tier_c.s90_market_creation import MarketCreationAlpha
from strategies.tier_c.s91_dispute_monitoring import DisputeMonitoring
from strategies.tier_c.s92_cross_chain_arb import CrossChainArbitrage
from strategies.tier_c.s93_tournament_signal import TournamentSignal
from strategies.tier_c.s94_volatility_surface import VolatilitySurface
from strategies.tier_c.s95_market_depth import MarketDepthAnalysis
from strategies.tier_c.s96_closing_line_value import ClosingLineValue
from strategies.tier_c.s97_smart_contract_event import SmartContractEventMonitor
from strategies.tier_c.s98_multi_timeframe import MultiTimeframeAnalysis
from strategies.tier_c.s99_portfolio_insurance import PortfolioInsurance
from strategies.tier_c.s100_meta_strategy import MetaStrategy


# --- S86: Cross-Market Correlation Matrix ---

def test_s86_scan_groups_by_category_and_finds_divergence():
    s = CorrelationMatrix()
    markets = [
        Market(condition_id="0x1", question="Team A wins?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}], category="NBA", active=True),
        Market(condition_id="0x2", question="Team B wins?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.70"}], category="NBA", active=True),
        Market(condition_id="0x3", question="Will it rain?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.50"}], category="Weather", active=True),
    ]
    opps = s.scan(markets)
    # NBA avg = 0.50; 0x1 diverges by 0.20, 0x2 diverges by 0.20; Weather has only 1 market
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


# --- S87: ML Feature Engineering Pipeline ---

def test_s87_scan_extracts_features_for_active_markets():
    s = MLFeatureEngineering()
    markets = [
        Market(condition_id="0x1", question="Event A?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}], volume=5000, active=True),
        Market(condition_id="0x2", question="Event B?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].metadata["features"]["volume"] == 5000


# --- S88: Social Graph Analysis ---

def test_s88_scan_collects_all_active():
    s = SocialGraphAnalysis()
    markets = [
        Market(condition_id="0x1", question="Event?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], active=True),
        Market(condition_id="0x2", question="Closed?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=False),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S89: Polygon Gas Cost Optimization ---

def test_s89_analyze_blocks_high_gas():
    s = GasOptimization()
    opp = Opportunity(
        market_id="0x1", question="Event?", market_price=0.50,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "current_gas_gwei": 100,
            "pending_signal": {"side": "buy", "estimated_prob": 0.65},
        },
    )
    signal = s.analyze(opp)
    assert signal is None  # Gas too high


# --- S90: New Market Creation Alpha ---

def test_s90_scan_finds_new_markets():
    s = MarketCreationAlpha()
    markets = [
        Market(condition_id="0x1", question="New event?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50", "age_hours": 12}], active=True),
        Market(condition_id="0x2", question="Old event?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60", "age_hours": 48}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S91: UMA Dispute Monitoring ---

def test_s91_scan_finds_disputed_markets():
    s = DisputeMonitoring()
    markets = [
        Market(condition_id="0x1", question="Disputed?", description="Active UMA dispute ongoing", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x2", question="Normal?", description="Standard resolution", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S92: Cross-Chain Arbitrage ---

def test_s92_scan_finds_multi_chain_markets():
    s = CrossChainArbitrage()
    markets = [
        Market(condition_id="0x1", question="Multi-chain?", description="Also on Gnosis chain", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}], active=True),
        Market(condition_id="0x2", question="Single chain?", description="Polygon only", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.45"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S93: Prediction Tournament Signals ---

def test_s93_analyze_uses_tournament_consensus():
    s = TournamentSignal()
    opp = Opportunity(
        market_id="0x1", question="Tracked event?", market_price=0.40,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "tournament_consensus": 0.60,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == 0.60


# --- S94: Volatility Surface Analysis ---

def test_s94_scan_groups_related_tenors():
    s = VolatilitySurface()
    markets = [
        Market(condition_id="0x1", question="Will BTC be above 100K?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], end_date_iso="2026-06-01T00:00:00Z", active=True),
        Market(condition_id="0x2", question="Will BTC be above 120K?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.30"}], end_date_iso="2026-12-01T00:00:00Z", active=True),
        Market(condition_id="0x3", question="Will it rain?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.40"}], end_date_iso="2026-03-15T00:00:00Z", active=True),
    ]
    opps = s.scan(markets)
    # BTC markets share stem -> 2 opportunities
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


# --- S95: Market Depth Analysis ---

def test_s95_analyze_detects_bid_imbalance():
    s = MarketDepthAnalysis()
    opp = Opportunity(
        market_id="0x1", question="Event?", market_price=0.50,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "bid_depth": 80000,
            "ask_depth": 20000,
        },
    )
    signal = s.analyze(opp)
    # imbalance = (80000-20000)/100000 = 0.60 > 0.30
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob > 0.50


# --- S96: Closing Line Value Tracking ---

def test_s96_scan_finds_markets_near_resolution():
    s = ClosingLineValue()
    markets = [
        Market(condition_id="0x1", question="Resolving soon?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.80", "days_left": 2}], active=True),
        Market(condition_id="0x2", question="Far away?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60", "days_left": 30}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S97: Smart Contract Event Monitoring ---

def test_s97_scan_finds_onchain_markets():
    s = SmartContractEventMonitor()
    markets = [
        Market(condition_id="0x1", question="On-chain event?", description="Resolved via Chainlink oracle", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}], active=True),
        Market(condition_id="0x2", question="Manual event?", description="Resolved manually", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.45"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S98: Multi-Timeframe Analysis ---

def test_s98_analyze_aligned_trends():
    s = MultiTimeframeAnalysis()
    opp = Opportunity(
        market_id="0x1", question="Trending?", market_price=0.50,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "trend_short": 0.05,
            "trend_medium": 0.08,
            "trend_long": 0.04,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    # avg_trend = (0.05 + 0.08 + 0.04) / 3 ~= 0.0567
    assert signal.estimated_prob == pytest.approx(0.50 + 0.0567, abs=0.01)


# --- S99: Portfolio Insurance via NO Positions ---

def test_s99_scan_finds_correlated_cheap_no():
    s = PortfolioInsurance()
    markets = [
        Market(condition_id="0x1", question="Correlated risk?", tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.70"},
            {"token_id": "n1", "outcome": "No", "price": "0.30", "portfolio_correlation": 0.60},
        ], active=True),
        Market(condition_id="0x2", question="Uncorrelated?", tokens=[
            {"token_id": "y2", "outcome": "Yes", "price": "0.80"},
            {"token_id": "n2", "outcome": "No", "price": "0.20", "portfolio_correlation": 0.10},
        ], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


# --- S100: Meta-Strategy Weighted Ensemble ---

def test_s100_analyze_weighted_ensemble():
    s = MetaStrategy()
    opp = Opportunity(
        market_id="0x1", question="Ensemble?", market_price=0.40,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "sub_signals": [
                {"strategy": "s86", "prob": 0.60, "weight": 0.50},
                {"strategy": "s93", "prob": 0.70, "weight": 0.50},
            ],
        },
    )
    signal = s.analyze(opp)
    # weighted_prob = (0.60*0.50 + 0.70*0.50) / 1.0 = 0.65
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == pytest.approx(0.65, abs=0.01)
