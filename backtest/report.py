import math
from backtest.engine import BacktestResult

class BacktestReport:
    def __init__(self, result: BacktestResult):
        self.result = result

    @property
    def total_return(self) -> float:
        if self.result.initial_balance == 0:
            return 0.0
        return (self.result.final_balance - self.result.initial_balance) / self.result.initial_balance

    @property
    def total_trades(self) -> int:
        return len(self.result.trades)

    @property
    def win_rate(self) -> float:
        if not self.result.trades:
            return 0.0
        # Simplified: trades with positive expected edge
        wins = sum(1 for t in self.result.trades if t.price < 0.50)
        return wins / len(self.result.trades) if self.result.trades else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.result.equity_curve:
            return 0.0
        peak = self.result.equity_curve[0]
        max_dd = 0.0
        for val in self.result.equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        if len(self.result.equity_curve) < 2:
            return 0.0
        returns = []
        for i in range(1, len(self.result.equity_curve)):
            prev = self.result.equity_curve[i - 1]
            curr = self.result.equity_curve[i]
            if prev > 0:
                returns.append((curr - prev) / prev)
        if not returns:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0.0
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0
        if std_ret == 0:
            return 0.0
        return (mean_ret / std_ret) * math.sqrt(252)  # Annualized

    def summary(self) -> dict:
        return {
            "initial_balance": self.result.initial_balance,
            "final_balance": self.result.final_balance,
            "total_return": f"{self.total_return:.2%}",
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate:.2%}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
        }

    def to_text(self) -> str:
        s = self.summary()
        lines = ["=== Backtest Report ==="]
        for k, v in s.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
