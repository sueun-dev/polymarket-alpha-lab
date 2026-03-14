"""Lightweight market-channel websocket client for Polymarket CLOB."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from core.client import PolymarketClient


class ClobMarketStream:
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(self) -> None:
        self.logger = logging.getLogger("core.market_stream")

    async def stream_quotes(
        self,
        token_ids: List[str],
        duration_seconds: float = 10.0,
        callback: Optional[Callable[[str, Dict[str, Optional[float]], Dict[str, Any]], None]] = None,
    ) -> Dict[str, Dict[str, Optional[float]]]:
        token_ids = [str(token_id).strip() for token_id in token_ids if str(token_id).strip()]
        if not token_ids:
            return {}

        state: Dict[str, Dict[str, Optional[float]]] = {}
        deadline = asyncio.get_running_loop().time() + max(0.5, float(duration_seconds))
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.WS_URL, heartbeat=15) as ws:
                await ws.send_json(
                    {
                        "type": "market",
                        "assets_ids": token_ids,
                        "custom_feature_enabled": True,
                    }
                )
                while True:
                    timeout = deadline - asyncio.get_running_loop().time()
                    if timeout <= 0:
                        break
                    try:
                        msg = await ws.receive(timeout=timeout)
                    except asyncio.TimeoutError:
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        if msg.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                            break
                        continue
                    try:
                        payload = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    updates = self._normalize_updates(payload)
                    for token_id, quote, raw in updates:
                        state[token_id] = quote
                        if callback is not None:
                            callback(token_id, quote, raw)
        return state

    @staticmethod
    def _normalize_updates(payload: Any) -> List[tuple[str, Dict[str, Optional[float]], Dict[str, Any]]]:
        updates: List[tuple[str, Dict[str, Optional[float]], Dict[str, Any]]] = []
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    token_id = str(item.get("asset_id", "")).strip()
                    if not token_id:
                        continue
                    updates.append((token_id, PolymarketClient.summarize_orderbook(item), item))
            return updates

        if not isinstance(payload, dict):
            return updates

        token_id = str(payload.get("asset_id") or payload.get("token_id") or "").strip()
        if not token_id:
            return updates

        best_bid = payload.get("best_bid")
        best_ask = payload.get("best_ask")
        bid_size = payload.get("best_bid_size")
        ask_size = payload.get("best_ask_size")

        def _parse(value: Any) -> Optional[float]:
            try:
                return float(value)
            except Exception:
                return None

        quote = {
            "best_bid": _parse(best_bid),
            "best_ask": _parse(best_ask),
            "bid_size": _parse(bid_size),
            "ask_size": _parse(ask_size),
            "midpoint": None,
            "spread": None,
            "microprice": None,
        }
        if quote["best_bid"] is not None and quote["best_ask"] is not None:
            quote["midpoint"] = (quote["best_bid"] + quote["best_ask"]) / 2.0
            quote["spread"] = quote["best_ask"] - quote["best_bid"]
            total_size = (quote["bid_size"] or 0.0) + (quote["ask_size"] or 0.0)
            if total_size > 0:
                quote["microprice"] = ((quote["best_ask"] * (quote["bid_size"] or 0.0)) + (quote["best_bid"] * (quote["ask_size"] or 0.0))) / total_size
        updates.append((token_id, quote, payload))
        return updates
