import pytest
from datetime import datetime
from backtest.data_loader import DataLoader, HistoricalDataPoint
from backtest.simulator import TradeSimulator
from backtest.engine import BacktestEngine
from backtest.report import BacktestReport
from core.models import Market
from core.base_strategy import BaseStrategy
from core.models import Opportunity, Signal

class SimpleStrategy(BaseStrategy):
    name = "simple_test"
    tier = "S"
    strategy_id = 0
    required_data = []

    def scan(self, markets):
        return [Opportunity(market_id=m.condition_id, question=m.question, market_price=float(m.tokens[0].get("price", 0.5)) if m.tokens else 0.5, metadata={"tokens": m.tokens}) for m in markets]

    def analyze(self, opp):
        if opp.market_price < 0.40:
            tokens = opp.metadata.get("tokens", [])
            token_id = tokens[0].get("token_id", "") if tokens else ""
            return Signal(market_id=opp.market_id, token_id=token_id, side="buy", estimated_prob=0.60, market_price=opp.market_price, confidence=0.7, strategy_name=self.name)
        return None

    def execute(self, signal, size, client=None):
        return None

def test_simulator_fill():
    sim = TradeSimulator(slippage_pct=0.01, fee_pct=0.001)
    trade = sim.simulate_fill("m1", "buy", "yes", 0.50, 100.0)
    assert trade.price > 0.50  # slippage
    assert trade.fee > 0
    assert len(sim.trades) == 1

def test_engine_run():
    strategy = SimpleStrategy()
    engine = BacktestEngine(strategy=strategy, initial_balance=10000.0)
    data = [
        HistoricalDataPoint(
            timestamp=datetime(2026, 1, 1), market=Market(condition_id="m1", question="Test?", tokens=[{"token_id": "y1", "outcome": "Yes", "price": "0.30"}], volume=5000),
            yes_price=0.30, no_price=0.70, volume=5000,
        ),
    ]
    result = engine.run(data)
    assert result.initial_balance == 10000.0
    assert len(result.equity_curve) > 0

def test_report():
    from backtest.engine import BacktestResult
    result = BacktestResult()
    result.initial_balance = 10000.0
    result.final_balance = 11000.0
    result.equity_curve = [10000, 10200, 10100, 10500, 11000]
    report = BacktestReport(result)
    assert report.total_return == pytest.approx(0.10, abs=0.01)
    assert report.max_drawdown > 0
    assert "total_return" in report.summary()
