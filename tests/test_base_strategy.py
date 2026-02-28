# tests/test_base_strategy.py
import pytest
from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal
from strategies import StrategyRegistry

class MockStrategy(BaseStrategy):
    name = "mock"
    tier = "S"
    strategy_id = 0
    required_data = []

    def scan(self, markets):
        return [Opportunity(market_id=m.condition_id, question=m.question, market_price=0.5) for m in markets if m.volume > 1000]

    def analyze(self, opportunity):
        return Signal(market_id=opportunity.market_id, token_id="t1", side="buy", estimated_prob=0.70, market_price=0.50, confidence=0.8, strategy_name=self.name)

    def execute(self, signal, size, client=None):
        return None

def test_scan():
    s = MockStrategy()
    markets = [Market(condition_id="0x1", question="Test?", tokens=[], volume=5000)]
    assert len(s.scan(markets)) == 1

def test_size_position():
    s = MockStrategy()
    sig = Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.70, market_price=0.50, confidence=0.8, strategy_name="mock")
    size = s.size_position(sig, bankroll=10000)
    assert size > 0

def test_registry():
    reg = StrategyRegistry()
    reg.register(MockStrategy())
    assert reg.get("mock") is not None
    assert len(reg.get_all()) == 1
    assert len(reg.get_by_tier("S")) == 1
    assert len(reg.get_by_tier("A")) == 0
