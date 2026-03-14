# core/client.py
import os
import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from core.models import Market, Order, Position

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

    def _paper_position_for(self, token_id: str) -> Optional[dict]:
        for position in self._paper_positions:
            if str(position.get("token_id", "")).strip() == token_id:
                return position
        return None

    def _update_paper_position(
        self,
        *,
        token_id: str,
        market_id: Optional[str],
        side: str,
        price: float,
        size: float,
        strategy_name: str,
        position_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        existing = self._paper_position_for(token_id)
        if side.lower() == "buy":
            if existing is None:
                self._paper_positions.append(
                    {
                        "market_id": str(market_id or token_id),
                        "token_id": token_id,
                        "side": "buy",
                        "entry_price": float(price),
                        "size": float(size),
                        "current_price": float(price),
                        "strategy_name": strategy_name,
                        "metadata": dict(position_metadata or {}),
                    }
                )
                return

            old_size = float(existing.get("size", 0.0))
            new_size = old_size + float(size)
            if new_size <= 0:
                return
            old_entry = float(existing.get("entry_price", price))
            existing["entry_price"] = ((old_entry * old_size) + (float(price) * float(size))) / new_size
            existing["size"] = new_size
            existing["current_price"] = float(price)
            existing["market_id"] = str(market_id or existing.get("market_id") or token_id)
            existing["strategy_name"] = strategy_name or str(existing.get("strategy_name") or "")
            if position_metadata:
                meta = existing.get("metadata") or {}
                if isinstance(meta, dict):
                    meta.update(position_metadata)
                    existing["metadata"] = meta
            return

        if existing is None:
            return
        remaining = float(existing.get("size", 0.0)) - float(size)
        existing["current_price"] = float(price)
        if remaining <= 1e-9:
            self._paper_positions = [pos for pos in self._paper_positions if pos is not existing]
            return
        existing["size"] = remaining

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
                event_id = None
                tags: List[str] = []
                events = m.get("events", [])
                if isinstance(events, list):
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        if event_id is None and event.get("id") is not None:
                            event_id = str(event.get("id"))
                        if not m.get("resolutionSource") and event.get("resolutionSource"):
                            m["resolutionSource"] = event.get("resolutionSource")
                        if not m.get("description") and event.get("description"):
                            m["description"] = event.get("description")
                        for tag in event.get("tags", []) or []:
                            if not isinstance(tag, dict):
                                continue
                            label = str(tag.get("slug") or tag.get("label") or "").strip()
                            if label and label not in tags:
                                tags.append(label)
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
                    resolution_source=m.get("resolutionSource"),
                    event_id=event_id,
                    tags=tags,
                    enable_order_book=bool(m.get("enableOrderBook", False)),
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

    def get_orderbooks(self, token_ids: List[str]) -> List[dict]:
        payload = [{"token_id": str(token_id)} for token_id in token_ids if str(token_id).strip()]
        if not payload:
            return []
        resp = self._http.post(f"{self.BASE_URL}/books", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return body if isinstance(body, list) else []

    def get_midpoint(self, token_id: str) -> Optional[float]:
        resp = self._http.get(f"{self.BASE_URL}/midpoint", params={"token_id": token_id})
        resp.raise_for_status()
        payload = resp.json()
        raw = payload.get("mid") if isinstance(payload, dict) else None
        try:
            return float(raw)
        except Exception:
            return None

    def get_price(self, token_id: str, side: str = "buy") -> Optional[float]:
        resp = self._http.get(
            f"{self.BASE_URL}/price",
            params={"token_id": token_id, "side": str(side).lower()},
        )
        resp.raise_for_status()
        payload = resp.json()
        raw = payload.get("price") if isinstance(payload, dict) else None
        try:
            return float(raw)
        except Exception:
            return None

    def get_prices(self, requests: List[Dict[str, str]]) -> Dict[str, Dict[str, float]]:
        payload = []
        for item in requests:
            token_id = str(item.get("token_id", "")).strip()
            if not token_id:
                continue
            row: Dict[str, str] = {"token_id": token_id}
            side = str(item.get("side", "")).strip()
            if side:
                row["side"] = side.upper()
            payload.append(row)
        if not payload:
            return {}
        resp = self._http.post(f"{self.BASE_URL}/prices", json=payload)
        resp.raise_for_status()
        raw_body = resp.json()
        result: Dict[str, Dict[str, float]] = {}
        if not isinstance(raw_body, dict):
            return result
        for token_id, side_map in raw_body.items():
            if not isinstance(side_map, dict):
                continue
            parsed_side_map: Dict[str, float] = {}
            for side, raw_price in side_map.items():
                try:
                    parsed_side_map[str(side).upper()] = float(raw_price)
                except Exception:
                    continue
            if parsed_side_map:
                result[str(token_id)] = parsed_side_map
        return result

    @staticmethod
    def summarize_orderbook(book: Dict[str, Any]) -> Dict[str, Optional[float]]:
        def _best(levels: Any, choose_max: bool) -> tuple[Optional[float], Optional[float]]:
            best_price = None
            best_size = None
            if not isinstance(levels, list):
                return best_price, best_size
            for row in levels:
                if not isinstance(row, dict):
                    continue
                try:
                    price = float(row.get("price"))
                    size = float(row.get("size"))
                except Exception:
                    continue
                if best_price is None or (price > best_price if choose_max else price < best_price):
                    best_price = price
                    best_size = size
            return best_price, best_size

        best_bid, bid_size = _best(book.get("bids"), choose_max=True)
        best_ask, ask_size = _best(book.get("asks"), choose_max=False)
        midpoint = None
        if best_bid is not None and best_ask is not None:
            midpoint = (best_bid + best_ask) / 2.0
        spread = None
        microprice = None
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            total_size = (bid_size or 0.0) + (ask_size or 0.0)
            if total_size > 0:
                microprice = ((best_ask * (bid_size or 0.0)) + (best_bid * (ask_size or 0.0))) / total_size
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "midpoint": midpoint,
            "spread": spread,
            "microprice": microprice,
        }

    def quote_token(self, token_id: str) -> Dict[str, Optional[float]]:
        summary = self.summarize_orderbook(self.get_orderbook(token_id))
        if summary.get("midpoint") is None:
            summary["midpoint"] = self.get_midpoint(token_id)
        return summary

    def quote_tokens(self, token_ids: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        quotes: Dict[str, Dict[str, Optional[float]]] = {}
        books = self.get_orderbooks(token_ids)
        for book in books:
            if not isinstance(book, dict):
                continue
            asset_id = str(book.get("asset_id", "")).strip()
            if not asset_id:
                continue
            quotes[asset_id] = self.summarize_orderbook(book)
        return quotes

    def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        strategy_name: str = "",
        order_type: str = "GTC",
        market_id: Optional[str] = None,
        position_metadata: Optional[Dict[str, Any]] = None,
    ) -> Order:
        order = Order(
            market_id=str(market_id or token_id),
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            strategy_name=strategy_name,
            timestamp=datetime.now(),
        )
        if not self.is_live:
            order.status = "paper"
            order.order_id = f"paper_{len(self._paper_orders)}"
            self._paper_orders.append(order)
            cost = price * size
            if side == "buy":
                self._paper_balance -= cost
            else:
                self._paper_balance += cost
            self._update_paper_position(
                token_id=token_id,
                market_id=market_id,
                side=side,
                price=price,
                size=size,
                strategy_name=strategy_name,
                position_metadata=position_metadata,
            )
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
            order_type_const = getattr(OrderType, str(order_type).upper(), OrderType.GTC)
            response = self._clob_client.post_order(signed_order, order_type_const)

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

    def get_positions(self) -> List[Position]:
        if not self.is_live:
            return [
                Position(
                    market_id=str(raw.get("market_id", raw.get("token_id", ""))),
                    token_id=str(raw.get("token_id", "")),
                    side=str(raw.get("side", "buy")),
                    entry_price=float(raw.get("entry_price", 0.0)),
                    size=float(raw.get("size", 0.0)),
                    current_price=float(raw.get("current_price", raw.get("entry_price", 0.0))),
                    strategy_name=str(raw.get("strategy_name", "")),
                )
                for raw in self._paper_positions
            ]
        return []

    def close(self) -> None:
        try:
            self._http.close()
        except Exception:
            pass
