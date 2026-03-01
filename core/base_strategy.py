# core/base_strategy.py
from abc import ABC, abstractmethod
from typing import List, Optional
from core.models import Market, Opportunity, Signal, Order
from core.kelly import KellyCriterion

class BaseStrategy(ABC):
    name: str = "base"
    tier: str = "C"
    strategy_id: int = 0
    required_data: List[str] = []

    def __init__(self):
        self.kelly = KellyCriterion(fraction=0.25)

    @abstractmethod
    def scan(self, markets: List[Market]) -> List[Opportunity]:
        ...

    @abstractmethod
    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        ...

    @abstractmethod
    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        ...

    def set_data_registry(self, registry) -> None:
        """Inject the data registry. Called by main.py during initialization."""
        self._data_registry = registry

    def get_data(self, name: str):
        """Get a data provider by name. Returns None if no registry or provider not found.

        This is backward-compatible: returns None when no registry is set,
        so existing tests and strategies work unchanged.
        """
        registry = getattr(self, "_data_registry", None)
        if registry is None:
            return None
        return registry.get(name)

    def size_position(self, signal: Signal, bankroll: float) -> float:
        return self.kelly.bet_amount(bankroll=bankroll, p=signal.estimated_prob, market_price=signal.market_price)
