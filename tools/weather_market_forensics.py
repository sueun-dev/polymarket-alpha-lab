#!/usr/bin/env python3
"""Forensic back-analysis for Polymarket temperature markets.

Purpose:
1. Pull resolved temperature markets from Gamma.
2. Fetch YES token price histories from CLOB.
3. Evaluate simple pre-close entry rules at fixed horizons.

This does not claim to reproduce any private trader's exact system.
It quantifies what worked on publicly available market data.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.historical_fetcher import HistoricalFetcher, normalize_yes_no
from data.http_utils import http_get_json, parse_close_ts, parse_float, parse_json_array


GAMMA_BASE = "https://gamma-api.polymarket.com"


TEMPERATURE_Q_RE = re.compile(
    r"^Will the highest temperature in .+ on .+\?$",
    re.IGNORECASE,
)


@dataclass
class TempMarket:
    market_id: str
    question: str
    close_ts: int
    yes_token: str
    yes_won: bool
    volume: float


@dataclass
class EvalStats:
    side: str
    horizon_hours: int
    threshold: float
    trades: int
    hit_rate: float
    gross_cost: float
    pnl: float
    roi: float


@dataclass
class EntryPoint:
    market_id: str
    yes_won: bool
    yes_prices: dict[int, float]


def _iter_closed_markets(page_size: int = 500, max_rows: int = 30000) -> Iterable[dict[str, Any]]:
    offset = 0
    yielded = 0
    while yielded < max_rows:
        params = {
            "closed": "true",
            "archived": "false",
            "limit": str(page_size),
            "offset": str(offset),
            "order": "id",
            "ascending": "false",
        }
        url = f"{GAMMA_BASE}/markets?{urllib.parse.urlencode(params)}"
        batch = http_get_json(url)
        if not isinstance(batch, list) or not batch:
            break
        for row in batch:
            if isinstance(row, dict):
                yield row
                yielded += 1
                if yielded >= max_rows:
                    return
        if len(batch) < page_size:
            break
        offset += len(batch)


def _parse_temp_market(row: dict[str, Any]) -> Optional[TempMarket]:
    question = str(row.get("question") or "").strip()
    if not question or not TEMPERATURE_Q_RE.match(question):
        return None

    outcomes = parse_json_array(row.get("outcomes"))
    token_ids = parse_json_array(row.get("clobTokenIds"))
    prices = parse_json_array(row.get("outcomePrices"))
    if len(outcomes) != 2 or len(token_ids) != 2 or len(prices) != 2:
        return None

    idx = normalize_yes_no(outcomes)
    yes_i = idx.get("yes")
    no_i = idx.get("no")
    if yes_i is None or no_i is None:
        return None

    final_yes = parse_float(prices[yes_i])
    final_no = parse_float(prices[no_i])
    if final_yes is None or final_no is None:
        return None
    if max(final_yes, final_no) < 0.9:
        return None

    yes_token = str(token_ids[yes_i]).strip()
    if not yes_token:
        return None

    close_ts = (
        parse_close_ts(row.get("closedTime"))
        or parse_close_ts(row.get("endDate"))
        or parse_close_ts(row.get("endDateIso"))
    )
    if close_ts is None:
        return None

    market_id = str(row.get("id") or "").strip()
    if not market_id:
        return None

    volume = float(row.get("volumeNum", row.get("volume", 0)) or 0.0)
    return TempMarket(
        market_id=market_id,
        question=question,
        close_ts=close_ts,
        yes_token=yes_token,
        yes_won=final_yes > final_no,
        volume=volume,
    )


def collect_temperature_markets(max_rows: int, max_markets: int) -> list[TempMarket]:
    out: list[TempMarket] = []
    for row in _iter_closed_markets(max_rows=max_rows):
        parsed = _parse_temp_market(row)
        if parsed is not None:
            out.append(parsed)
            if len(out) >= max_markets:
                break
    out.sort(key=lambda x: x.close_ts)
    return out


def build_entry_points(
    markets: list[TempMarket],
    fetcher: HistoricalFetcher,
    horizons: list[int],
) -> list[EntryPoint]:
    points: list[EntryPoint] = []
    for market in markets:
        history = fetcher.load_or_fetch_history(market.yes_token)
        if len(history) < 2:
            continue
        price_map: dict[int, float] = {}
        for horizon in horizons:
            entry_ts = market.close_ts - (horizon * 3600)
            yes_price = fetcher.price_at_or_before(history, entry_ts)
            if yes_price is None:
                continue
            price_map[horizon] = max(0.0, min(1.0, float(yes_price)))
        if price_map:
            points.append(EntryPoint(market_id=market.market_id, yes_won=market.yes_won, yes_prices=price_map))
    return points


def eval_rule(
    entries: list[EntryPoint],
    side: str,
    horizon_hours: int,
    threshold: float,
) -> EvalStats:
    assert side in {"yes", "no"}
    trades = 0
    wins = 0
    gross_cost = 0.0
    pnl = 0.0

    for entry in entries:
        yes_price = entry.yes_prices.get(horizon_hours)
        if yes_price is None:
            continue

        if side == "yes":
            if yes_price > threshold:
                continue
            cost = yes_price
            payout = 1.0 if entry.yes_won else 0.0
            hit = entry.yes_won
        else:
            if yes_price < threshold:
                continue
            no_price = 1.0 - yes_price
            cost = no_price
            payout = 1.0 if not entry.yes_won else 0.0
            hit = not entry.yes_won

        if cost <= 0:
            continue

        trades += 1
        if hit:
            wins += 1
        gross_cost += cost
        pnl += (payout - cost)

    hit_rate = (wins / trades) if trades else 0.0
    roi = (pnl / gross_cost) if gross_cost > 0 else 0.0
    return EvalStats(
        side=side,
        horizon_hours=horizon_hours,
        threshold=threshold,
        trades=trades,
        hit_rate=hit_rate,
        gross_cost=gross_cost,
        pnl=pnl,
        roi=roi,
    )


def run_grid(entries: list[EntryPoint], min_trades: int) -> list[EvalStats]:
    results: list[EvalStats] = []
    horizons = [24, 12, 6, 3, 1]
    yes_thresholds = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    no_thresholds = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

    for horizon in horizons:
        for th in yes_thresholds:
            stat = eval_rule(entries, "yes", horizon, th)
            if stat.trades >= min_trades:
                results.append(stat)
        for th in no_thresholds:
            stat = eval_rule(entries, "no", horizon, th)
            if stat.trades >= min_trades:
                results.append(stat)

    results.sort(key=lambda x: (x.pnl, x.roi, x.trades), reverse=True)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket weather market forensic analysis")
    parser.add_argument("--max-rows", type=int, default=30000, help="Max closed Gamma rows to scan")
    parser.add_argument("--max-markets", type=int, default=600, help="Max temperature markets to analyze")
    parser.add_argument("--min-trades", type=int, default=40, help="Minimum trades required for a rule")
    parser.add_argument("--top-k", type=int, default=20, help="How many top rules to print")
    parser.add_argument("--report-path", default="logs/weather_forensics_report.json")
    args = parser.parse_args()

    fetcher = HistoricalFetcher()
    markets = collect_temperature_markets(max_rows=args.max_rows, max_markets=args.max_markets)
    horizons = [24, 12, 6, 3, 1]
    entries = build_entry_points(markets, fetcher, horizons)
    results = run_grid(entries, min_trades=args.min_trades)

    top = results[: max(1, args.top_k)]
    payload = {
        "scanned_closed_rows": args.max_rows,
        "temperature_markets_used": len(markets),
        "temperature_markets_with_entry_data": len(entries),
        "min_trades": args.min_trades,
        "top_rules": [asdict(x) for x in top],
        "example_markets": [asdict(m) for m in markets[-10:]],
    }

    out = Path(args.report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"temperature_markets_used={len(markets)}")
    for idx, row in enumerate(top, start=1):
        print(
            f"{idx:02d} side={row.side:<3} h={row.horizon_hours:>2}h th={row.threshold:.2f} "
            f"trades={row.trades:>4} hit={row.hit_rate:.3f} pnl={row.pnl:.3f} roi={row.roi:.3f}"
        )
    print(f"report={out}")


if __name__ == "__main__":
    main()
