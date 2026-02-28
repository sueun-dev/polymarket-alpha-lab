# core/scanner.py
import logging
from typing import List, Dict, Optional
from core.client import PolymarketClient
from core.models import Market

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, client: PolymarketClient, min_volume: float = 1000, min_liquidity: float = 0, categories: Optional[List[str]] = None):
        self.client = client
        self.min_volume = min_volume
        self.min_liquidity = min_liquidity
        self.categories = categories or []
        self._price_cache: Dict[str, float] = {}

    def scan(self, limit: int = 100) -> List[Market]:
        markets = self.client.get_markets(limit=limit, active_only=True)
        return [m for m in markets if self._passes_filter(m)]

    def _passes_filter(self, market: Market) -> bool:
        if not market.active:
            return False
        if market.volume < self.min_volume:
            return False
        if market.liquidity < self.min_liquidity:
            return False
        if self.categories and market.category not in self.categories:
            return False
        return True

    def is_price_spike(self, prev_price: float, curr_price: float, threshold: float = 0.15) -> bool:
        return abs(curr_price - prev_price) >= threshold

    def update_price_cache(self, market_id: str, price: float) -> Optional[float]:
        prev = self._price_cache.get(market_id)
        self._price_cache[market_id] = price
        return prev
