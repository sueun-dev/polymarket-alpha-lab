from core.base_strategy import BaseStrategy
from core.risk import RiskManager
from core.models import Market
from backtest.data_loader import DataLoader, HistoricalDataPoint
from backtest.simulator import TradeSimulator

class BacktestResult:
    def __init__(self):
        self.trades = []
        self.equity_curve = []
        self.initial_balance = 0.0
        self.final_balance = 0.0

class BacktestEngine:
    def __init__(self, strategy: BaseStrategy, initial_balance: float = 10000.0, slippage: float = 0.005):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.simulator = TradeSimulator(slippage_pct=slippage)
        self.risk = RiskManager()

    def run(self, data: list[HistoricalDataPoint]) -> BacktestResult:
        result = BacktestResult()
        result.initial_balance = self.initial_balance
        result.equity_curve.append(self.balance)
        for dp in sorted(data, key=lambda x: x.timestamp):
            markets = [dp.market]
            opportunities = self.strategy.scan(markets)
            for opp in opportunities:
                signal = self.strategy.analyze(opp)
                if signal is None:
                    continue
                if not self.risk.can_trade(signal, bankroll=self.balance, current_positions=[]):
                    continue
                size = self.strategy.size_position(signal, bankroll=self.balance)
                if size <= 0:
                    continue
                trade = self.simulator.simulate_fill(
                    market_id=signal.market_id, side=signal.side,
                    token=signal.token_id, price=signal.market_price,
                    size=size, strategy_name=self.strategy.name,
                    timestamp=dp.timestamp,
                )
                self.balance -= trade.total_cost
                result.trades.append(trade)
            result.equity_curve.append(self.balance)
        result.final_balance = self.balance
        return result
