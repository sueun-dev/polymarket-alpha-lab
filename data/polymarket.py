import logging
import json
from typing import List, Optional

import httpx

from core.models import Market

logger = logging.getLogger(__name__)

class PolymarketMarketDataClient:
    """Read-only Polymarket market-data client.

    This repository is strategy/research focused. The client intentionally
    excludes wallet credentials and order placement.
    """

    CLOB_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        self._http = httpx.Client(
            timeout=httpx.Timeout(3.0, connect=1.0),
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=64),
            headers={"User-Agent": "polymarket-research/1.0"},
        )

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
        resp = self._http.get(f"{self.CLOB_URL}/book", params={"token_id": token_id})
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        try:
            self._http.close()
        except Exception:
            pass
