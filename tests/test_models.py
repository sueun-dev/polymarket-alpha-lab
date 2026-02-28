# tests/test_models.py
import pytest
from core.models import Market, Signal, Opportunity, Order, Position

def test_market_creation():
    m = Market(condition_id="0x123", question="Will BTC hit 100K?", tokens=[{"token_id": "yes_id", "outcome": "Yes"}], active=True, volume=50000.0)
    assert m.condition_id == "0x123"
    assert m.active is True

def test_signal_edge():
    s = Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.70, market_price=0.55, confidence=0.8, strategy_name="test")
    assert s.edge == pytest.approx(0.15, abs=0.001)

def test_order_total_cost():
    o = Order(market_id="0x1", token_id="t1", side="buy", price=0.55, size=100.0, strategy_name="test")
    assert o.total_cost == pytest.approx(55.0, abs=0.01)

def test_position_pnl():
    p = Position(market_id="0x1", token_id="t1", side="buy", entry_price=0.55, size=100.0, current_price=0.65, strategy_name="test")
    assert p.unrealized_pnl == pytest.approx(10.0, abs=0.01)

def test_no_edge():
    s = Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.50, market_price=0.55, confidence=0.5, strategy_name="test")
    assert s.edge < 0
