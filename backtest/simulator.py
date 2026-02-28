from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SimulatedTrade:
    timestamp: datetime
    market_id: str
    side: str  # buy/sell
    token: str  # yes/no
    price: float
    size: float
    slippage: float
    fee: float
    total_cost: float
    strategy_name: str

@dataclass
class TradeSimulator:
    slippage_pct: float = 0.005  # 0.5% default
    fee_pct: float = 0.0001  # 0.01%
    trades: list = field(default_factory=list)

    def simulate_fill(self, market_id: str, side: str, token: str, price: float, size: float, strategy_name: str = "", timestamp: datetime = None) -> SimulatedTrade:
        slippage = price * self.slippage_pct
        fee = price * size * self.fee_pct
        fill_price = price + slippage if side == "buy" else price - slippage
        total_cost = fill_price * size + fee
        trade = SimulatedTrade(
            timestamp=timestamp or datetime.now(),
            market_id=market_id, side=side, token=token,
            price=fill_price, size=size, slippage=slippage,
            fee=fee, total_cost=total_cost, strategy_name=strategy_name,
        )
        self.trades.append(trade)
        return trade
