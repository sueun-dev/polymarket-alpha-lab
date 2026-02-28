import pytest
from core.models import Market, Opportunity
from strategies.tier_b.s61_volmex_volatility import VolmexVolatilityTrading
from strategies.tier_b.s62_settlement_cross_platform import SettlementCrossPlatformArb
from strategies.tier_b.s63_correlated_parlay import CorrelatedParlayMispricing
from strategies.tier_b.s64_oscar_specialization import OscarAwardsSpecialization
from strategies.tier_b.s65_earnings_analysis import DeepEarningsAnalysis
from strategies.tier_b.s66_crypto_regulatory import CryptoRegulatorySpecialization
from strategies.tier_b.s67_time_decay_certain import TimeDecayCertainOutcome
from strategies.tier_b.s68_flash_crash_bot import FlashCrashBot
from strategies.tier_b.s69_geopolitical_special import GeopoliticalSpecialization
from strategies.tier_b.s70_options_synthetic import OptionsSyntheticPositions


# --- S61: Volmex Implied Volatility Trading ---

def test_s61_scan_volatility_keywords():
    s = VolmexVolatilityTrading()
    markets = [
        Market(condition_id="0x1", question="Will BTC volatility exceed 80%?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40"}], active=True),
        Market(condition_id="0x2", question="Volmex implied vol above 60?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.55"}], active=True),
        Market(condition_id="0x3", question="Will it rain tomorrow?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.30"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


def test_s61_analyze_implied_vs_historical():
    s = VolmexVolatilityTrading()
    opp = Opportunity(
        market_id="0x1", question="BTC vol above 80%?", market_price=0.40,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "implied_vol": 0.30,
            "historical_vol": 0.50,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "y1"


# --- S62: Cross-Platform Settlement Rule Arbitrage ---

def test_s62_scan_cross_platform():
    s = SettlementCrossPlatformArb()
    markets = [
        Market(condition_id="0x1", question="Will X happen?", description="Also listed on Kalshi", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x2", question="Will Y happen?", description="No cross listing", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s62_analyze_with_price_diff():
    s = SettlementCrossPlatformArb()
    opp = Opportunity(
        market_id="0x1", question="Will X happen?", market_price=0.50,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "other_platform_price": 0.60},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == 0.60


# --- S63: Correlated Parlay Mispricing ---

def test_s63_scan_groups_by_category():
    s = CorrelatedParlayMispricing()
    markets = [
        Market(condition_id="0x1", question="Team A wins?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], category="NBA", active=True),
        Market(condition_id="0x2", question="Team B wins?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60"}], category="NBA", active=True),
        Market(condition_id="0x3", question="Will it rain?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.40"}], category="Weather", active=True),
    ]
    opps = s.scan(markets)
    # Only NBA category has 2+ markets -> 2 opportunities
    assert len(opps) == 2
    assert all(o.category == "nba" for o in opps)


def test_s63_analyze_with_correlation():
    s = CorrelatedParlayMispricing()
    opp = Opportunity(
        market_id="0x1", question="Team A wins?", market_price=0.50,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "correlation": 0.50,
            "parlay_market_price": 0.40,
        },
    )
    signal = s.analyze(opp)
    # fair_parlay_price = 0.50 + 0.50 * 0.10 = 0.55, edge = 0.55 - 0.40 = 0.15
    assert signal is not None
    assert signal.side == "buy"


# --- S64: Oscar/Awards Show Specialization ---

def test_s64_scan_award_keywords():
    s = OscarAwardsSpecialization()
    markets = [
        Market(condition_id="0x1", question="Will Oppenheimer win Best Picture Oscar?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.70"}], active=True),
        Market(condition_id="0x2", question="Will the Fed cut rates?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], active=True),
        Market(condition_id="0x3", question="Emmy for best drama series?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.35"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x3" in ids


def test_s64_analyze_with_precursors():
    s = OscarAwardsSpecialization()
    opp = Opportunity(
        market_id="0x1", question="Best Picture Oscar?", market_price=0.50,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "precursor_wins": 8, "total_precursors": 10},
    )
    signal = s.analyze(opp)
    # precursor_rate = 0.8, boost = 0.8 * 0.12 = 0.096, estimated = 0.596, edge = 0.096
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob > 0.50


# --- S65: Deep Earnings Analysis ---

def test_s65_scan_earnings_keywords():
    s = DeepEarningsAnalysis()
    markets = [
        Market(condition_id="0x1", question="Will MSFT beat Q2 earnings?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], active=True),
        Market(condition_id="0x2", question="Will Bitcoin hit 200K?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.10"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s65_analyze_composite_score():
    s = DeepEarningsAnalysis()
    opp = Opportunity(
        market_id="0x1", question="MSFT Q2 earnings beat?", market_price=0.55,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "revenue_trend_score": 0.80,
            "guidance_quality_score": 0.75,
            "sector_score": 0.70,
            "margin_score": 0.80,
        },
    )
    signal = s.analyze(opp)
    # composite = 0.80*0.30 + 0.75*0.25 + 0.70*0.20 + 0.80*0.25 = 0.7675
    # edge = 0.7675 - 0.55 = 0.2175 > 0.05
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == pytest.approx(0.7675, abs=0.01)


# --- S66: Crypto Regulatory Outcome Specialization ---

def test_s66_scan_regulatory_keywords():
    s = CryptoRegulatorySpecialization()
    markets = [
        Market(condition_id="0x1", question="Will the SEC approve a Bitcoin ETF?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.65"}], active=True),
        Market(condition_id="0x2", question="Will it snow in NYC?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.40"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s66_analyze_with_regulatory_score():
    s = CryptoRegulatorySpecialization()
    opp = Opportunity(
        market_id="0x1", question="SEC approve Bitcoin ETF?", market_price=0.55,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "regulatory_score": 0.75},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == 0.75


# --- S67: Time Decay on Near-Certain Outcomes ---

def test_s67_scan_high_yes_short_expiry():
    s = TimeDecayCertainOutcome()
    markets = [
        Market(condition_id="0x1", question="Near certain event?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.92"}], end_date_iso="2026-03-07T00:00:00Z", active=True),
        Market(condition_id="0x2", question="Uncertain event?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.50"}], end_date_iso="2026-03-07T00:00:00Z", active=True),
        Market(condition_id="0x3", question="Far future event?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.95"}], end_date_iso="2027-01-01T00:00:00Z", active=True),
    ]
    opps = s.scan(markets)
    # Only 0x1: YES > 0.90 AND within 14 days
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s67_analyze_theta_edge():
    s = TimeDecayCertainOutcome()
    opp = Opportunity(
        market_id="0x1", question="Near certain event?", market_price=0.92,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "days_left": 3.0},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob > 0.92


# --- S68: Flash Crash Detection and Buying ---

def test_s68_scan_detects_crash():
    s = FlashCrashBot()
    markets = [
        Market(
            condition_id="0x1", question="Flash crashed market?",
            tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.40", "prior_price": 0.70}],
            volume=10000, active=True,
        ),
        Market(
            condition_id="0x2", question="Stable market?",
            tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.60", "prior_price": 0.62}],
            volume=10000, active=True,
        ),
    ]
    opps = s.scan(markets)
    # 0x1: drop = (0.70 - 0.40) / 0.70 = 0.4286 > 0.20 -> detected
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s68_analyze_recovery():
    s = FlashCrashBot()
    opp = Opportunity(
        market_id="0x1", question="Flash crashed?", market_price=0.40,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "prior_price": 0.70,
            "drop_pct": 0.4286,
        },
    )
    signal = s.analyze(opp)
    # recovery_target = 0.40 + (0.70 - 0.40) * 0.70 = 0.61
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == pytest.approx(0.61, abs=0.01)


# --- S69: Geopolitical Event Specialization ---

def test_s69_scan_geopolitical_keywords():
    s = GeopoliticalSpecialization()
    markets = [
        Market(condition_id="0x1", question="Will a ceasefire be reached in 2026?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}], active=True),
        Market(condition_id="0x2", question="New NATO treaty signed?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.25"}], active=True),
        Market(condition_id="0x3", question="Will Apple release a new phone?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.90"}], active=True),
    ]
    opps = s.scan(markets)
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


def test_s69_analyze_with_geo_score():
    s = GeopoliticalSpecialization()
    opp = Opportunity(
        market_id="0x1", question="Ceasefire in 2026?", market_price=0.30,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes"}], "geo_score": 0.50},
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.estimated_prob == 0.50


# --- S70: Options-Style Synthetic Positions ---

def test_s70_scan_groups_related_markets():
    s = OptionsSyntheticPositions()
    markets = [
        Market(condition_id="0x1", question="Will BTC be above 100K?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], active=True),
        Market(condition_id="0x2", question="Will BTC be above 120K?", tokens=[{"token_id": "y2", "outcome": "Yes", "price": "0.30"}], active=True),
        Market(condition_id="0x3", question="Will it rain tomorrow?", tokens=[{"token_id": "y3", "outcome": "Yes", "price": "0.40"}], active=True),
    ]
    opps = s.scan(markets)
    # BTC markets share stem "will btc be above" -> 2 opportunities
    assert len(opps) == 2
    ids = [o.market_id for o in opps]
    assert "0x1" in ids
    assert "0x2" in ids


def test_s70_analyze_synthetic_spread():
    s = OptionsSyntheticPositions()
    opp = Opportunity(
        market_id="0x1", question="BTC above 100K?", market_price=0.60,
        metadata={
            "tokens": [{"token_id": "y1", "outcome": "Yes"}],
            "related_prices": [0.30],
            "synthetic_cost": 0.50,
            "fair_value": 0.60,
        },
    )
    signal = s.analyze(opp)
    # edge = 0.60 - 0.50 = 0.10 > 0.04
    assert signal is not None
    assert signal.side == "buy"
