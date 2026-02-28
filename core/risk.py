# core/risk.py
from typing import List
from core.models import Signal, Position

class RiskManager:
    def __init__(self, max_position_pct: float = 0.10, max_daily_loss_pct: float = 0.05, max_open_positions: int = 20, min_edge: float = 0.05):
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions
        self.min_edge = min_edge
        self._daily_loss = 0.0

    def can_trade(self, signal: Signal, bankroll: float, current_positions: List[Position]) -> bool:
        if signal.edge < self.min_edge:
            return False
        if len(current_positions) >= self.max_open_positions:
            return False
        if self._daily_loss >= bankroll * self.max_daily_loss_pct:
            return False
        if any(p.market_id == signal.market_id for p in current_positions):
            return False
        return True

    def max_position_size(self, bankroll: float, price: float) -> float:
        max_cost = bankroll * self.max_position_pct
        return max_cost / price if price > 0 else 0.0

    def record_loss(self, amount: float) -> None:
        self._daily_loss += amount

    def reset_daily(self) -> None:
        self._daily_loss = 0.0
