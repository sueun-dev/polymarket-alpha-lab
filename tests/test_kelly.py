# tests/test_kelly.py
import pytest
from core.kelly import KellyCriterion

def test_full_kelly():
    k = KellyCriterion()
    f = k.full_kelly(p=0.70, market_price=0.50)
    assert f == pytest.approx(0.40, abs=0.01)

def test_half_kelly():
    k = KellyCriterion()
    f = k.half_kelly(p=0.70, market_price=0.50)
    assert f == pytest.approx(0.20, abs=0.01)

def test_quarter_kelly():
    k = KellyCriterion(fraction=0.25, max_fraction=0.25)
    f = k.optimal_size(p=0.70, market_price=0.50)
    assert f == pytest.approx(0.10, abs=0.01)

def test_no_edge():
    k = KellyCriterion()
    f = k.full_kelly(p=0.50, market_price=0.55)
    assert f == 0.0

def test_bet_amount():
    k = KellyCriterion(fraction=0.25, max_fraction=0.25)
    amount = k.bet_amount(bankroll=10000, p=0.70, market_price=0.50)
    assert amount == pytest.approx(1000.0, abs=1.0)

def test_max_cap():
    k = KellyCriterion(fraction=0.5, max_fraction=0.06)
    f = k.optimal_size(p=0.95, market_price=0.50)
    assert f <= 0.06
