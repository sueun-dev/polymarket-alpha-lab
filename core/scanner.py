# core/scanner.py
import logging
from typing import List, Dict, Optional
from core.client import PolymarketClient
from core.models import Market

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(
        self,
        client: PolymarketClient,
        min_volume: float = 1000,
        min_liquidity: float = 0,
        categories: Optional[List[str]] = None,
        page_size: int = 200,
        order_by: str = "volume",
        ascending: bool = False,
    ):
        self.client = client
        self.min_volume = min_volume
        self.min_liquidity = min_liquidity
        self.categories = categories or []
        self.page_size = max(1, int(page_size))
        self.order_by = order_by
        self.ascending = ascending
        self._price_cache: Dict[str, float] = {}

    def scan(self, limit: int = 100) -> List[Market]:
        markets: List[Market] = []
        offset = 0
        seen_ids = set()
        target = max(1, int(limit))
        while len(markets) < target:
            batch_limit = min(self.page_size, target - len(markets))
            batch = self.client.get_markets(
                limit=batch_limit,
                active_only=True,
                offset=offset,
                order_by=self.order_by,
                ascending=self.ascending,
            )
            if not batch:
                break
            for market in batch:
                if market.condition_id in seen_ids:
                    continue
                seen_ids.add(market.condition_id)
                if self._passes_filter(market):
                    markets.append(market)
                    if len(markets) >= target:
                        break
            if len(batch) < batch_limit:
                break
            offset += len(batch)
        return markets

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
