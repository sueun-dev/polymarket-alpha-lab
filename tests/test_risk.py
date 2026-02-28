# tests/test_risk.py
import pytest
from core.risk import RiskManager
from core.models import Signal, Position

def _signal(edge=0.15):
    return Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.50+edge, market_price=0.50, confidence=0.8, strategy_name="test")

def test_allows_valid():
    rm = RiskManager()
    assert rm.can_trade(_signal(), bankroll=10000, current_positions=[]) is True

def test_blocks_low_edge():
    rm = RiskManager(min_edge=0.05)
    assert rm.can_trade(_signal(edge=0.03), bankroll=10000, current_positions=[]) is False

def test_blocks_max_positions():
    rm = RiskManager(max_open_positions=2)
    positions = [Position(market_id=f"0x{i}", token_id=f"t{i}", side="buy", entry_price=0.5, size=100, current_price=0.5, strategy_name="t") for i in range(2)]
    assert rm.can_trade(_signal(), bankroll=10000, current_positions=positions) is False

def test_daily_loss():
    rm = RiskManager(max_daily_loss_pct=0.05)
    rm.record_loss(600)
    assert rm.can_trade(_signal(), bankroll=10000, current_positions=[]) is False

def test_max_position_size():
    rm = RiskManager(max_position_pct=0.10)
    assert rm.max_position_size(bankroll=10000, price=0.50) == pytest.approx(2000.0, abs=1.0)

def test_blocks_duplicate_market():
    rm = RiskManager()
    positions = [Position(market_id="0x1", token_id="t1", side="buy", entry_price=0.5, size=100, current_price=0.5, strategy_name="t")]
    assert rm.can_trade(_signal(), bankroll=10000, current_positions=positions) is False
