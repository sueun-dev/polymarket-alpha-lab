import pytest
from core.models import Market, Opportunity
from strategies.tier_s.s06_btc_latency_arb import BTCLatencyArb
from strategies.tier_s.s07_settlement_rules import SettlementRules
from strategies.tier_s.s08_domain_specialization import DomainSpecialization
from strategies.tier_s.s09_oracle_latency import OracleLatency
from strategies.tier_s.s10_yes_bias import YesBiasExploitation

def test_s06_scan_btc():
    s = BTCLatencyArb()
    markets = [Market(condition_id="0x1", question="BTC 15-minute price above $100K?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.55"}], volume=5000)]
    opps = s.scan(markets)
    assert len(opps) == 1

def test_s06_analyze_placeholder():
    s = BTCLatencyArb()
    opp = Opportunity(market_id="0x1", question="BTC?", market_price=0.55, metadata={"tokens": []})
    assert s.analyze(opp) is None

def test_s07_scan():
    s = SettlementRules()
    markets = [Market(condition_id="0x1", question="Bitcoin reserve?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], volume=10000, description="Resolves YES if government officially announces reserve")]
    opps = s.scan(markets)
    assert len(opps) == 1

def test_s08_domain_filter():
    s = DomainSpecialization(focus_domain="crypto")
    markets = [
        Market(condition_id="0x1", question="Will Bitcoin hit 200K?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}], volume=5000),
        Market(condition_id="0x2", question="Will Lakers win?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.60"}], volume=5000),
    ]
    opps = s.scan(markets)
    assert len(opps) == 1
    assert opps[0].market_id == "0x1"

def test_s09_scan_hourly():
    s = OracleLatency()
    markets = [Market(condition_id="0x1", question="BTC hourly close above 100K?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.50"}], volume=5000)]
    opps = s.scan(markets)
    assert len(opps) == 1

def test_s10_scan_exciting():
    s = YesBiasExploitation()
    markets = [Market(condition_id="0x1", question="First ever Mars landing by 2027?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.35"}, {"token_id": "n1", "outcome": "No", "price": "0.65"}], volume=10000)]
    opps = s.scan(markets)
    assert len(opps) == 1

def test_s10_analyze_bets_no():
    s = YesBiasExploitation()
    opp = Opportunity(market_id="0x1", question="First ever?", market_price=0.35, metadata={"tokens": [{"token_id": "n1", "outcome": "No"}], "exciting": True})
    signal = s.analyze(opp)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.token_id == "n1"

def test_s10_no_edge_returns_none():
    s = YesBiasExploitation()
    opp = Opportunity(market_id="0x1", question="Normal question?", market_price=0.20, metadata={"tokens": [{"token_id": "n1", "outcome": "No"}], "exciting": False})
    signal = s.analyze(opp)
    # no_price = 0.80, base_no = 0.70, edge = -0.10 -> None
    assert signal is None
