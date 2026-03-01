"""Historical market fetcher with local price-history cache."""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from data.base_provider import BaseDataProvider
from data.http_utils import http_get_json, parse_close_ts, parse_float, parse_json_array


@dataclass
class MarketSample:
    """A resolved binary market with its YES token and outcome."""

    market_id: str
    question: str
    category: str
    close_ts: int
    yes_token: str
    yes_won: bool


def normalize_yes_no(outcomes: Sequence[object]) -> Dict[str, int]:
    """Map outcome labels to their positional index.

    Recognises common variants: Yes/No, YES/NO, y/n, true/false, 1/0.
    Returns a dict with up to two keys: ``"yes"`` and ``"no"``.
    """
    norm: Dict[str, int] = {}
    for i, raw in enumerate(outcomes):
        name = str(raw).strip().lower()
        name = "".join(ch for ch in name if ch.isalnum())
        if name in {"yes", "y", "true", "1"}:
            norm["yes"] = i
        elif name in {"no", "n", "false", "0"}:
            norm["no"] = i
    return norm


class HistoricalFetcher(BaseDataProvider):
    """Fetch closed binary markets and their price histories from Polymarket APIs.

    Extends :class:`BaseDataProvider` with methods for retrieving historical
    market data from the Gamma and CLOB APIs, plus a local JSON-file cache
    for price histories.
    """

    name = "historical_fetcher"

    GAMMA_BASE = "https://gamma-api.polymarket.com"
    CLOB_BASE = "https://clob.polymarket.com"

    def __init__(self, cache_dir: Path | None = None) -> None:
        super().__init__()
        self.cache_dir = cache_dir or Path("data/cache/")

    # ------------------------------------------------------------------
    # BaseDataProvider interface
    # ------------------------------------------------------------------

    def fetch(self, **kwargs: Any) -> Any:
        """Main entry point -- delegates to :meth:`fetch_closed_binary_markets`."""
        max_markets = kwargs.get("max_markets", 1200)
        page_size = kwargs.get("page_size", 500)
        return self.fetch_closed_binary_markets(
            max_markets=max_markets, page_size=page_size
        )

    # ------------------------------------------------------------------
    # Market fetching
    # ------------------------------------------------------------------

    def fetch_closed_binary_markets(
        self, max_markets: int = 1200, page_size: int = 500
    ) -> List[MarketSample]:
        """Return up to *max_markets* resolved binary markets, oldest first."""
        samples: List[MarketSample] = []
        offset = 0

        while len(samples) < max_markets:
            params = {
                "closed": "true",
                "limit": str(page_size),
                "offset": str(offset),
                "order": "id",
                "ascending": "false",
            }
            url = f"{self.GAMMA_BASE}/markets?{urllib.parse.urlencode(params)}"
            batch = http_get_json(url)
            if not isinstance(batch, list) or not batch:
                break

            for m in batch:
                if not isinstance(m, dict):
                    continue

                outcomes = parse_json_array(m.get("outcomes"))
                token_ids = parse_json_array(m.get("clobTokenIds"))
                prices = parse_json_array(m.get("outcomePrices"))
                if len(outcomes) != 2 or len(token_ids) != 2 or len(prices) != 2:
                    continue

                idx = normalize_yes_no(outcomes)
                # Prefer YES token when available, otherwise anchor to outcome index 0.
                anchor_i = idx.get("yes", 0)
                other_i = 1 - anchor_i

                anchor_final = parse_float(prices[anchor_i])
                other_final = parse_float(prices[other_i])
                if anchor_final is None or other_final is None:
                    continue

                # Keep only clearly resolved final outcomes.
                if max(anchor_final, other_final) < 0.9:
                    continue
                yes_won = anchor_final > other_final

                token = str(token_ids[anchor_i]).strip()
                if not token:
                    continue

                close_ts = (
                    parse_close_ts(m.get("closedTime"))
                    or parse_close_ts(m.get("endDate"))
                    or parse_close_ts(m.get("endDateIso"))
                )
                if close_ts is None:
                    continue

                category = str(m.get("category") or "unknown")
                question = str(m.get("question") or "")
                market_id = str(m.get("id") or "")
                if not market_id:
                    continue

                samples.append(
                    MarketSample(
                        market_id=market_id,
                        question=question,
                        category=category,
                        close_ts=close_ts,
                        yes_token=token,
                        yes_won=yes_won,
                    )
                )
                if len(samples) >= max_markets:
                    break

            if len(batch) < page_size:
                break
            offset += len(batch)

        # Sort oldest -> newest for chronological split
        samples.sort(key=lambda x: x.close_ts)
        return samples

    # ------------------------------------------------------------------
    # Price history with file cache
    # ------------------------------------------------------------------

    def load_or_fetch_history(
        self, token: str, fidelity: int = 1
    ) -> List[Tuple[int, float]]:
        """Load price history from local cache or fetch from CLOB API.

        The history is cached as a JSON file under
        ``<cache_dir>/histories/<token>.json``.
        """
        cache_path = self.cache_dir / "histories" / f"{token}.json"
        if cache_path.exists():
            try:
                raw = json.loads(cache_path.read_text())
                if isinstance(raw, list):
                    out: List[Tuple[int, float]] = []
                    for item in raw:
                        if isinstance(item, list) and len(item) == 2:
                            t = int(item[0])
                            p = float(item[1])
                            out.append((t, p))
                    if out:
                        return out
            except Exception:
                pass

        params = {
            "market": token,
            "interval": "max",
            "fidelity": str(fidelity),
        }
        url = f"{self.CLOB_BASE}/prices-history?{urllib.parse.urlencode(params)}"
        payload = http_get_json(url)
        history: List[Tuple[int, float]] = []
        if isinstance(payload, dict):
            rows = payload.get("history")
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    t = parse_float(row.get("t"))
                    p = parse_float(row.get("p"))
                    if t is None or p is None:
                        continue
                    history.append((int(t), float(p)))

        history.sort(key=lambda x: x[0])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(history))
        return history

    # ------------------------------------------------------------------
    # Price look-up helpers (static -- no instance state needed)
    # ------------------------------------------------------------------

    @staticmethod
    def price_at_or_before(
        history: Sequence[Tuple[int, float]], target_ts: int
    ) -> Optional[float]:
        """Binary-search for the price at or just before *target_ts*."""
        if not history:
            return None
        lo = 0
        hi = len(history) - 1
        if history[0][0] > target_ts:
            return None
        if history[-1][0] <= target_ts:
            return history[-1][1]

        while lo <= hi:
            mid = (lo + hi) // 2
            t = history[mid][0]
            if t == target_ts:
                return history[mid][1]
            if t < target_ts:
                lo = mid + 1
            else:
                hi = mid - 1

        if hi < 0:
            return None
        return history[hi][1]

    @staticmethod
    def window_prices(
        history: Sequence[Tuple[int, float]], start_ts: int, end_ts: int
    ) -> List[float]:
        """Return all prices in the closed interval ``[start_ts, end_ts]``."""
        if not history:
            return []
        out: List[float] = []
        for t, p in history:
            if t < start_ts:
                continue
            if t > end_ts:
                break
            out.append(p)
        return out
