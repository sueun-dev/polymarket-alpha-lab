"""S06 deprecated: BTC short-horizon latency strategy has been removed.

This repository now prioritizes weather/NOAA workflows and does not run
5-minute BTC market prediction logic.
"""
from __future__ import annotations

from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Order, Signal


class BTCLatencyArb(BaseStrategy):
    """Compatibility placeholder.

    Keeps the strategy registry stable (S06 id/name/path) while disabling all
    BTC 5-minute prediction behavior.
    """

    name = "s06_btc_latency_arb"
    tier = "S"
    strategy_id = 6
    required_data: list[str] = []

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        return []

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        return None
