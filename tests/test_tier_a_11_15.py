import pytest
from core.models import Market, Opportunity
from strategies.tier_a.s11_superforecaster import SuperforecasterMethod
from strategies.tier_a.s12_high_prob_harvesting import HighProbHarvesting
from strategies.tier_a.s13_vitalik_anti_irrational import VitalikAntiIrrational
from strategies.tier_a.s14_cultural_regional_bias import CulturalRegionalBias
from strategies.tier_a.s15_news_mean_reversion import NewsMeanReversion


# S11 Tests
def test_s11_scan_finds_quantifiable():
    s = SuperforecasterMethod()
    markets = [Market(
        condition_id="0x1",
        question="Will inflation reach 5% by December 2026?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.40"},
            {"token_id": "n1", "outcome": "No", "price": "0.60"},
        ],
        end_date_iso="2026-12-31T00:00:00Z",
        volume=10000,
        category="economics",
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"


def test_s11_analyze_produces_signal_with_edge():
    s = SuperforecasterMethod()
    # YES price 0.80 in economics (base rate 0.40)
    # Bayesian: 0.60*0.40 + 0.40*0.80 = 0.24 + 0.32 = 0.56
    # Edge YES = 0.56 - 0.80 = -0.24 (YES overpriced) -> buy NO
    opp = Opportunity(
        market_id="0x1",
        question="Will GDP growth exceed 4%?",
        market_price=0.80,
        category="economics",
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ],
            "end_date_iso": "2026-12-31T00:00:00Z",
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"  # Buy NO since YES is overpriced
    assert signal.edge > 0


# S12 Tests
def test_s12_scan_finds_high_prob():
    s = HighProbHarvesting()
    markets = [Market(
        condition_id="0x1",
        question="Will the sun rise tomorrow?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.97"},
            {"token_id": "n1", "outcome": "No", "price": "0.03"},
        ],
        end_date_iso="2026-03-01T00:00:00Z",
        volume=5000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_price == 0.97


def test_s12_analyze_signals_buy_near_resolution():
    s = HighProbHarvesting()
    opp = Opportunity(
        market_id="0x1",
        question="Will the sun rise tomorrow?",
        market_price=0.97,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.97"},
                {"token_id": "n1", "outcome": "No", "price": "0.03"},
            ],
            "days_left": 3.0,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "y1"
    assert signal.estimated_prob == 0.99
    assert signal.metadata["annualized_yield"] > 0


# S13 Tests
def test_s13_scan_finds_absurd():
    s = VitalikAntiIrrational()
    markets = [Market(
        condition_id="0x1",
        question="Will aliens destroy the Earth by 2027?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.15"},
            {"token_id": "n1", "outcome": "No", "price": "0.85"},
        ],
        volume=2000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert "alien" in opps[0].metadata["matched_keywords"]


def test_s13_analyze_bets_no_on_absurd():
    s = VitalikAntiIrrational()
    opp = Opportunity(
        market_id="0x1",
        question="Will a zombie apocalypse happen?",
        market_price=0.20,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.20"},
                {"token_id": "n1", "outcome": "No", "price": "0.80"},
            ],
            "matched_keywords": ["zombie"],
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"  # Buy NO
    assert signal.estimated_prob == 0.98  # 1 - 0.02 absurd true prob
    assert signal.confidence == 0.80


# S14 Tests
def test_s14_scan_finds_non_us():
    s = CulturalRegionalBias()
    markets = [Market(
        condition_id="0x1",
        question="Will France hold early elections in 2026?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.45"},
            {"token_id": "n1", "outcome": "No", "price": "0.55"},
        ],
        volume=3000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert "france" in opps[0].metadata["matched_keywords"]


def test_s14_analyze_flags_for_review():
    s = CulturalRegionalBias()
    opp = Opportunity(
        market_id="0x1",
        question="Will Japan raise interest rates?",
        market_price=0.50,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.50"},
                {"token_id": "n1", "outcome": "No", "price": "0.50"},
            ],
            "matched_keywords": ["japan"],
            "volume": 800,  # Low volume -> extra edge
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"
    assert signal.confidence == 0.50  # Lower confidence, needs review
    assert signal.metadata["requires_manual_review"] is True


# S15 Tests
def test_s15_scan_finds_price_spike():
    s = NewsMeanReversion()
    markets = [Market(
        condition_id="0x1",
        question="Will the Fed cut rates in March?",
        tokens=[
            {"token_id": "y1", "outcome": "Yes", "price": "0.70", "price_change_24h": "0.20"},
            {"token_id": "n1", "outcome": "No", "price": "0.30"},
        ],
        volume=50000,
    )]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].metadata["price_change_24h"] == 0.20


def test_s15_analyze_fades_upward_spike():
    s = NewsMeanReversion()
    opp = Opportunity(
        market_id="0x1",
        question="Will the Fed cut rates?",
        market_price=0.70,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.70"},
                {"token_id": "n1", "outcome": "No", "price": "0.30"},
            ],
            "price_change_24h": 0.20,
            "previous_price": 0.50,
        },
    )
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"  # Fading the upward move -> buy NO
    assert signal.metadata["expected_reversion"] == pytest.approx(0.10)
