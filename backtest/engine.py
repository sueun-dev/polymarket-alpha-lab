from core.base_strategy import BaseStrategy
from core.kelly import KellyCriterion, dollars_to_shares
from core.models import Position
from backtest.data_loader import HistoricalDataPoint
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
        self.kelly = KellyCriterion(fraction=0.25)
        self.min_edge = 0.05
        self.max_open_positions = 20

    def run(self, data: list[HistoricalDataPoint]) -> BacktestResult:
        result = BacktestResult()
        result.initial_balance = self.initial_balance
        result.equity_curve.append(self.balance)
        open_positions: list[Position] = []
        for dp in sorted(data, key=lambda x: x.timestamp):
            markets = [dp.market]
            opportunities = self.strategy.scan(markets)
            for opp in opportunities:
                signal = self.strategy.analyze(opp)
                if signal is None:
                    continue
                if signal.edge < self.min_edge:
                    continue
                if len(open_positions) >= self.max_open_positions:
                    continue
                if any(p.market_id == signal.market_id for p in open_positions):
                    continue
                stake_usd = self.kelly.bet_amount(
                    bankroll=self.balance,
                    p=signal.estimated_prob,
                    market_price=signal.market_price,
                )
                size = dollars_to_shares(stake_usd, signal.market_price)
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
                open_positions.append(Position(
                    market_id=signal.market_id, token_id=signal.token_id,
                    side=signal.side, entry_price=signal.market_price,
                    size=size, current_price=signal.market_price,
                    strategy_name=self.strategy.name,
                ))
            result.equity_curve.append(self.balance)
        result.final_balance = self.balance
        return result
