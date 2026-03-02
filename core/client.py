# core/client.py
import os
import logging
import json
from typing import List, Optional
from datetime import datetime

import httpx

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
        self._http = httpx.Client(
            timeout=httpx.Timeout(3.0, connect=1.0),
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=64),
            headers={"User-Agent": "polymarket-research/1.0"},
        )
        if self.is_live:
            self._init_live_client()

    def _init_live_client(self):
        try:
            from py_clob_client.client import ClobClient

            api_key = os.environ.get("POLYMARKET_API_KEY", "")
            chain_id = int(os.environ.get("POLYMARKET_CHAIN_ID", "137"))
            signature_type = int(os.environ.get("POLYMARKET_SIGNATURE_TYPE", "0"))
            funder = os.environ.get("POLYMARKET_FUNDER", "").strip()

            kwargs = {}
            if funder:
                kwargs["funder"] = funder
            if signature_type:
                kwargs["signature_type"] = signature_type

            self._clob_client = ClobClient(self.BASE_URL, key=api_key, chain_id=chain_id, **kwargs)

            # Required in most setups to sign authenticated order requests.
            if hasattr(self._clob_client, "create_or_derive_api_creds") and hasattr(self._clob_client, "set_api_creds"):
                creds = self._clob_client.create_or_derive_api_creds()
                self._clob_client.set_api_creds(creds)
        except Exception as e:
            logger.error(f"Failed to init live client: {e}")
            raise

    def get_markets(
        self,
        limit: int = 100,
        active_only: bool = True,
        offset: int = 0,
        order_by: Optional[str] = None,
        ascending: Optional[bool] = None,
    ) -> List[Market]:
        raw = self._fetch_markets(
            limit=limit,
            active_only=active_only,
            offset=offset,
            order_by=order_by,
            ascending=ascending,
        )
        markets = []
        for m in raw:
            try:
                tokens = m.get("tokens", [])
                if not tokens:
                    tokens = self._build_tokens_from_gamma(m)
                markets.append(Market(
                    condition_id=m.get("condition_id", m.get("conditionId", m.get("id", ""))),
                    question=m.get("question", ""),
                    slug=m.get("slug", ""),
                    tokens=tokens,
                    end_date_iso=m.get("end_date_iso", m.get("endDate", m.get("endDateIso"))),
                    active=m.get("active", True),
                    volume=float(m.get("volumeNum", m.get("volume", 0))),
                    liquidity=float(m.get("liquidityNum", m.get("liquidity", 0))),
                    category=m.get("category", ""),
                    description=m.get("description", ""),
                ))
            except Exception:
                continue
        return markets

    def _build_tokens_from_gamma(self, market: dict) -> List[dict]:
        outcomes = market.get("outcomes", [])
        prices = market.get("outcomePrices", [])
        token_ids = market.get("clobTokenIds", [])

        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                outcomes = []
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                prices = []
        if isinstance(token_ids, str):
            try:
                token_ids = json.loads(token_ids)
            except Exception:
                token_ids = []

        n = min(len(outcomes), len(prices), len(token_ids))
        tokens: List[dict] = []
        for i in range(n):
            try:
                price = float(prices[i])
            except Exception:
                price = 0.0
            tokens.append(
                {
                    "token_id": str(token_ids[i]),
                    "outcome": str(outcomes[i]),
                    "price": str(price),
                }
            )
        return tokens

    def _fetch_markets(
        self,
        limit: int = 100,
        active_only: bool = True,
        offset: int = 0,
        order_by: Optional[str] = None,
        ascending: Optional[bool] = None,
    ) -> List[dict]:
        params = {
            "limit": limit,
            "offset": max(0, int(offset)),
            "closed": "false",
            "archived": "false",
        }
        if active_only:
            params["active"] = "true"
        if order_by:
            params["order"] = str(order_by)
        if ascending is not None:
            params["ascending"] = "true" if bool(ascending) else "false"
        resp = self._http.get(f"{self.GAMMA_URL}/markets", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_orderbook(self, token_id: str) -> dict:
        return self._fetch_orderbook(token_id)

    def _fetch_orderbook(self, token_id: str) -> dict:
        resp = self._http.get(f"{self.BASE_URL}/book", params={"token_id": token_id})
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

        if self._clob_client is None:
            order.status = "rejected"
            logger.error("Live order rejected: CLOB client not initialized")
            return order

        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY, SELL

            side_const = BUY if side.lower() == "buy" else SELL
            order_args = OrderArgs(
                token_id=token_id,
                price=round(float(price), 4),
                size=round(float(size), 4),
                side=side_const,
            )
            signed_order = self._clob_client.create_order(order_args)
            response = self._clob_client.post_order(signed_order, OrderType.GTC)

            order.status = "live"
            if isinstance(response, dict):
                raw_id = response.get("orderID") or response.get("id") or response.get("order_id")
                if raw_id is not None:
                    order.order_id = str(raw_id)
            logger.info(f"[LIVE] {side} {size}x @ {price} | {strategy_name}")
            return order
        except Exception as exc:
            order.status = "rejected"
            logger.error(f"Live order failed: {exc}")
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

    def close(self) -> None:
        try:
            self._http.close()
        except Exception:
            pass
