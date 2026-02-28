# core/client.py
import os
import logging
from typing import List, Dict
from datetime import datetime
from core.models import Market, Order

logger = logging.getLogger(__name__)

class PolymarketClient:
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self, mode: str = "paper", paper_balance: float = 10000.0):
        self.mode = mode
        self.is_live = mode == "live"
        self._paper_balance = paper_balance
        self._paper_positions: List[dict] = []
        self._paper_orders: List[Order] = []
        self._clob_client = None
        if self.is_live:
            self._init_live_client()

    def _init_live_client(self):
        try:
            from py_clob_client.client import ClobClient
            api_key = os.environ.get("POLYMARKET_API_KEY", "")
            secret = os.environ.get("POLYMARKET_SECRET", "")
            chain_id = int(os.environ.get("POLYMARKET_CHAIN_ID", "137"))
            self._clob_client = ClobClient(self.BASE_URL, key=api_key, chain_id=chain_id)
        except Exception as e:
            logger.error(f"Failed to init live client: {e}")
            raise

    def get_markets(self, limit: int = 100, active_only: bool = True) -> List[Market]:
        raw = self._fetch_markets(limit=limit, active_only=active_only)
        markets = []
        for m in raw:
            try:
                markets.append(Market(
                    condition_id=m.get("condition_id", m.get("id", "")),
                    question=m.get("question", ""),
                    tokens=m.get("tokens", []),
                    end_date_iso=m.get("end_date_iso"),
                    active=m.get("active", True),
                    volume=float(m.get("volume", 0)),
                    liquidity=float(m.get("liquidity", 0)),
                    category=m.get("category", ""),
                    description=m.get("description", ""),
                ))
            except Exception:
                continue
        return markets

    def _fetch_markets(self, limit: int = 100, active_only: bool = True) -> List[dict]:
        import httpx
        params = {"limit": limit, "active": active_only}
        resp = httpx.get(f"{self.GAMMA_URL}/markets", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_orderbook(self, token_id: str) -> dict:
        return self._fetch_orderbook(token_id)

    def _fetch_orderbook(self, token_id: str) -> dict:
        import httpx
        resp = httpx.get(f"{self.BASE_URL}/book", params={"token_id": token_id})
        resp.raise_for_status()
        return resp.json()

    def place_order(self, token_id: str, side: str, price: float, size: float, strategy_name: str = "") -> Order:
        order = Order(market_id=token_id, token_id=token_id, side=side, price=price, size=size, strategy_name=strategy_name, timestamp=datetime.now())
        if not self.is_live:
            order.status = "paper"
            order.order_id = f"paper_{len(self._paper_orders)}"
            self._paper_orders.append(order)
            cost = price * size
            if side == "buy":
                self._paper_balance -= cost
            else:
                self._paper_balance += cost
            logger.info(f"[PAPER] {side} {size}x @ {price} | {strategy_name}")
            return order
        return order

    def get_balance(self) -> float:
        if not self.is_live:
            return self._paper_balance
        return 0.0

    def get_positions(self) -> List[dict]:
        if not self.is_live:
            return self._paper_positions
        return []
