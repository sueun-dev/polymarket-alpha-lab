#!/usr/bin/env python3
"""Fast live runner for S02 using batch CLOB pricing and optional terminal monitoring."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.client import PolymarketClient
from core.market_stream import ClobMarketStream
from core.weather_catalog import catalog_rows_to_markets, filter_catalog_rows, load_catalog
from data import DataRegistry
from data.aviationweather import AviationWeatherProvider
from data.global_climate import GlobalClimateProvider
from data.nws_climate import NWSClimateProvider
from data.weather_router import WeatherRouterProvider
from strategies.tier_s.s02_weather_noaa import WeatherNOAA

LOCAL_TZ = ZoneInfo("America/New_York")


def build_registry() -> DataRegistry:
    registry = DataRegistry()
    registry.register(WeatherRouterProvider())
    registry.register(AviationWeatherProvider())
    registry.register(NWSClimateProvider())
    registry.register(GlobalClimateProvider())
    return registry


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_iso_date(value: Any) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except Exception:
        return None


def _format_remaining(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    if seconds <= 0:
        return "closed"
    whole = int(seconds)
    days = whole // 86400
    hours = (whole % 86400) // 3600
    minutes = (whole % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _market_timing_fields(opportunity: Any) -> Dict[str, Any]:
    metadata = opportunity.metadata if hasattr(opportunity, "metadata") else {}
    contract = metadata.get("weather_contract") if isinstance(metadata, dict) else {}
    contract = contract if isinstance(contract, dict) else {}
    target_date = _parse_iso_date(contract.get("target_date"))
    end_dt = _parse_iso_datetime(metadata.get("end_date_iso"))
    now_local = datetime.now(LOCAL_TZ)
    cutoff_local = end_dt.astimezone(LOCAL_TZ) if end_dt is not None else None
    seconds_left = (cutoff_local - now_local).total_seconds() if cutoff_local is not None else None
    target_state = "-"
    if target_date is not None:
        local_today = now_local.date()
        delta_days = (target_date - local_today).days
        if delta_days == 0:
            target_state = "today"
        elif delta_days == 1:
            target_state = "tomorrow"
        elif delta_days > 1:
            target_state = f"in_{delta_days}d"
        else:
            target_state = "past"
    return {
        "target_date": target_date.isoformat() if target_date is not None else contract.get("target_date"),
        "target_day_state": target_state,
        "cutoff_iso": end_dt.isoformat() if end_dt is not None else metadata.get("end_date_iso"),
        "cutoff_local": cutoff_local.strftime("%Y-%m-%d %H:%M %Z") if cutoff_local is not None else None,
        "seconds_to_cutoff": None if seconds_left is None else round(seconds_left, 1),
        "time_to_cutoff": _format_remaining(seconds_left),
    }


def load_markets(client: PolymarketClient, limit: int, page_size: int) -> List[Any]:
    markets: List[Any] = []
    offset = 0
    while len(markets) < limit:
        batch = client.get_markets(
            limit=min(page_size, max(1, limit - len(markets))),
            active_only=True,
            offset=offset,
            order_by="volume",
            ascending=False,
        )
        if not batch:
            break
        markets.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return markets[:limit]


def load_filtered_catalog_rows(
    catalog_path: str,
    city: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    supported_only: bool = False,
) -> List[Dict[str, Any]]:
    path = Path(catalog_path)
    if not path.exists():
        return []
    payload = load_catalog(path)
    return filter_catalog_rows(
        payload,
        city=city,
        country=country,
        region=region,
        supported_only=supported_only,
    )


def filter_markets_with_catalog(
    markets: List[Any],
    catalog_rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Any]:
    if catalog_rows is None:
        return markets
    wanted = {str(row.get("condition_id")) for row in catalog_rows}
    if not wanted:
        return []
    return [market for market in markets if market.condition_id in wanted]


def load_markets_from_catalog_rows(
    client: PolymarketClient,
    catalog_rows: List[Dict[str, Any]],
) -> List[Any]:
    return catalog_rows_to_markets(catalog_rows, client=client, refresh_quotes=True)


def _analyze_rows(
    strategy: WeatherNOAA,
    opportunities: List[Any],
    workers: int = 1,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    max_workers = max(1, int(workers))
    evaluator = getattr(strategy, "evaluate_opportunity", None)
    if evaluator is None:
        evaluator = lambda opp: {"status": "bettable", "reason_code": "pass", "reason": "-", "signal": strategy.analyze(opp)}
    if max_workers == 1:
        for opp in opportunities:
            evaluation = evaluator(opp)
            rows.append({"opportunity": opp, "signal": evaluation.get("signal"), "evaluation": evaluation})
        return rows

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        evaluations = list(executor.map(evaluator, opportunities))
    for opp, evaluation in zip(opportunities, evaluations):
        rows.append({"opportunity": opp, "signal": evaluation.get("signal"), "evaluation": evaluation})
    return rows


def _provider_call(provider: Any, method_name: str, city: str, country_code: Optional[str]) -> Any:
    if provider is None or not hasattr(provider, method_name):
        return None
    method = getattr(provider, method_name)
    if country_code:
        try:
            return method(city, country_code=country_code)
        except TypeError:
            return method(city)
    return method(city)


def _prewarm_catalog_weather(
    strategy: WeatherNOAA,
    catalog_rows: Optional[List[Dict[str, Any]]],
    workers: int,
) -> Dict[str, Any]:
    provider = strategy.get_data("noaa_weather") or strategy.get_data("noaa")
    if provider is None or not catalog_rows:
        return {"city_count": 0, "elapsed_ms": 0.0}

    unique_cities: List[tuple[str, Optional[str]]] = []
    seen = set()
    for row in catalog_rows:
        city = str(row.get("canonical_city") or row.get("city") or "").strip()
        if not city:
            continue
        country_code = str(row.get("country_code") or "").strip().lower() or None
        key = (city.lower(), country_code or "")
        if key in seen:
            continue
        seen.add(key)
        unique_cities.append((city, country_code))

    started = time.perf_counter()

    def _warm(item: tuple[str, Optional[str]]) -> None:
        city, country_code = item
        _provider_call(provider, "get_forecast", city, country_code)
        _provider_call(provider, "get_grid_data", city, country_code)
        _provider_call(provider, "get_latest_observation", city, country_code)

    max_workers = max(1, int(workers))
    if max_workers == 1:
        for item in unique_cities:
            _warm(item)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(_warm, unique_cities))

    return {
        "city_count": len(unique_cities),
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 1),
    }


def collect_live_snapshot(
    client: PolymarketClient,
    strategy: WeatherNOAA,
    max_markets: int,
    page_size: int,
    min_edge: float,
    min_confidence: float,
    catalog_rows: Optional[List[Dict[str, Any]]] = None,
    workers: int = 1,
) -> Dict[str, Any]:
    started = time.perf_counter()
    if catalog_rows is not None:
        markets = load_markets_from_catalog_rows(client, catalog_rows)
        quote_mode = "catalog_cached"
        catalog_count = len(catalog_rows)
    else:
        markets = load_markets(client, limit=max_markets, page_size=page_size)
        quote_mode = "clob_requote"
        catalog_count = None
    loaded_at = time.perf_counter()
    prewarm = _prewarm_catalog_weather(strategy, catalog_rows, workers=max(1, workers * 2))
    prewarmed_at = time.perf_counter()

    if hasattr(strategy, "scan_market_universe"):
        opportunities = strategy.scan_market_universe(markets, include_low_score=True)
    else:
        opportunities = strategy.scan(markets)
    rows = _analyze_rows(
        strategy=strategy,
        opportunities=opportunities,
        workers=workers,
    )
    analyzed_at = time.perf_counter()

    quotes = {}
    if quote_mode == "clob_requote":
        token_ids = [row["signal"].token_id for row in rows if row.get("signal") is not None]
        quotes = client.quote_tokens(token_ids)

    ranked: List[Dict[str, Any]] = []
    monitoring: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    for row in rows:
        evaluation = row.get("evaluation") or {}
        signal = row["signal"]
        timing = _market_timing_fields(row["opportunity"])
        base = {
            "question": row["opportunity"].question,
            "market_id": row["opportunity"].market_id,
            "status": evaluation.get("status"),
            "reason_code": evaluation.get("reason_code"),
            "reason": evaluation.get("reason"),
            "target_date": timing.get("target_date"),
            "target_day_state": timing.get("target_day_state"),
            "cutoff_iso": timing.get("cutoff_iso"),
            "cutoff_local": timing.get("cutoff_local"),
            "seconds_to_cutoff": timing.get("seconds_to_cutoff"),
            "time_to_cutoff": timing.get("time_to_cutoff"),
            "candidate_score": round(float(row["opportunity"].metadata.get("candidate_score", 0.0)), 4),
            "confidence": round(float(evaluation.get("confidence") or 0.0), 4),
            "max_edge": evaluation.get("max_edge"),
            "required_edge": evaluation.get("required_edge"),
            "city": row["opportunity"].metadata.get("city") or "",
            "weather_type": evaluation.get("weather_type") or row["opportunity"].metadata.get("weather_type"),
            "regime": evaluation.get("regime"),
        }
        if timing.get("seconds_to_cutoff") is not None and float(timing["seconds_to_cutoff"]) <= 0:
            blocked.append({**base, "status": "blocked", "reason_code": "cutoff_passed", "reason": "시장 cutoff가 지나서 더 이상 진입할 수 없습니다."})
            continue
        if signal is None:
            target = blocked if evaluation.get("status") == "blocked" else monitoring
            target.append(base)
            continue
        if signal.confidence < min_confidence:
            monitoring.append(
                {
                    **base,
                    "status": "monitor",
                    "reason_code": "confidence_below_runner_min",
                    "reason": "전략은 통과했지만 러너 최소 confidence보다 낮습니다.",
                    "confidence": round(signal.confidence, 4),
                }
            )
            continue
        quote = quotes.get(signal.token_id, {})
        best_ask = signal.market_price if quote_mode == "catalog_cached" else quote.get("best_ask")
        if best_ask is None and quote_mode != "catalog_cached":
            best_ask = client.get_price(signal.token_id, side="buy")
        if best_ask is None or best_ask <= 0:
            blocked.append({**base, "status": "blocked", "reason_code": "no_live_ask", "reason": "현재 체결 가능한 ask 호가가 없습니다."})
            continue
        live_edge = signal.estimated_prob - float(best_ask)
        if live_edge < min_edge:
            monitoring.append(
                {
                    **base,
                    "status": "monitor",
                    "reason_code": "live_edge_below_runner_min",
                    "reason": "실시간 체결 edge가 러너 최소 기준보다 낮습니다.",
                    "entry_price": round(float(best_ask), 4),
                    "best_ask": round(float(best_ask), 4),
                    "estimated_prob": round(signal.estimated_prob, 4),
                    "live_edge": round(live_edge, 4),
                    "token_id": signal.token_id,
                    "setup_type": signal.metadata.get("setup_type"),
                    "station_id": signal.metadata.get("station_id"),
                    "settlement_source": signal.metadata.get("settlement_source"),
                    "release_state": signal.metadata.get("release_state"),
                }
            )
            continue
        ranked.append(
            {
                **base,
                "token_id": signal.token_id,
                "signal": signal,
                "entry_price": round(float(best_ask), 4),
                "live_edge": round(live_edge, 4),
                "confidence": round(signal.confidence, 4),
                "estimated_prob": round(signal.estimated_prob, 4),
                "spread": None if quote.get("spread") is None else round(float(quote["spread"]), 4),
                "best_bid": None if quote.get("best_bid") is None else round(float(quote["best_bid"]), 4),
                "best_ask": round(float(best_ask), 4),
                "ask_size": None if quote.get("ask_size") is None else round(float(quote["ask_size"]), 4),
                "setup_type": signal.metadata.get("setup_type"),
                "regime": signal.metadata.get("regime"),
                "hold_to_expiry": bool(signal.metadata.get("hold_to_expiry")),
                "exit_style": signal.metadata.get("exit_style"),
                "take_profit_partial_price": signal.metadata.get("take_profit_partial_price"),
                "take_profit_price": signal.metadata.get("take_profit_price"),
                "review_below_price": signal.metadata.get("review_below_price"),
                "city": signal.metadata.get("city"),
                "station_id": signal.metadata.get("station_id"),
                "settlement_source": signal.metadata.get("settlement_source"),
                "settlement_location_id": signal.metadata.get("settlement_location_id"),
                "release_state": signal.metadata.get("release_state"),
                "source_count": signal.metadata.get("source_count"),
                "budget_cap_usd": round(float(signal.metadata.get("budget_cap_usd", 0.0)), 2),
            }
        )
    ranked.sort(key=lambda item: (item["live_edge"] * item["confidence"], item["live_edge"]), reverse=True)
    monitoring.sort(
        key=lambda item: (
            float(item.get("live_edge") or item.get("max_edge") or 0.0),
            float(item.get("confidence") or 0.0),
            float(item.get("candidate_score") or 0.0),
        ),
        reverse=True,
    )
    blocked.sort(
        key=lambda item: (
            float(item.get("candidate_score") or 0.0),
            float(item.get("confidence") or 0.0),
        ),
        reverse=True,
    )
    finished = time.perf_counter()
    return {
        "ranked": ranked,
        "monitoring": monitoring,
        "blocked": blocked,
        "market_count": len(markets),
        "opportunity_count": len(opportunities),
        "signal_count": sum(1 for row in rows if row.get("signal") is not None),
        "catalog_count": catalog_count,
        "quote_mode": quote_mode,
        "timings_ms": {
            "load_markets": round((loaded_at - started) * 1000.0, 1),
            "prewarm": round((prewarmed_at - loaded_at) * 1000.0, 1),
            "analyze": round((analyzed_at - prewarmed_at) * 1000.0, 1),
            "total": round((finished - started) * 1000.0, 1),
        },
        "prewarm": prewarm,
    }


def rank_live_entries(
    client: PolymarketClient,
    strategy: WeatherNOAA,
    max_markets: int,
    page_size: int,
    min_edge: float,
    min_confidence: float,
    catalog_rows: Optional[List[Dict[str, Any]]] = None,
    workers: int = 1,
) -> List[Dict[str, Any]]:
    snapshot = collect_live_snapshot(
        client=client,
        strategy=strategy,
        max_markets=max_markets,
        page_size=page_size,
        min_edge=min_edge,
        min_confidence=min_confidence,
        catalog_rows=catalog_rows,
        workers=workers,
    )
    return list(snapshot["ranked"])


def _json_safe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload.pop("signal", None)
        cleaned.append(payload)
    return cleaned


def execute_entry(
    client: PolymarketClient,
    strategy: WeatherNOAA,
    row: Dict[str, Any],
    bankroll: float,
    order_type: str,
) -> Optional[Dict[str, Any]]:
    signal = row["signal"].model_copy(update={"market_price": row["entry_price"]})
    raw_size = strategy.size_position(signal, bankroll=bankroll)
    budget_cap = float(signal.metadata.get("budget_cap_usd", strategy.BASE_BET))
    if raw_size <= 0 or row["entry_price"] <= 0:
        return None
    size = min(raw_size, budget_cap / row["entry_price"])
    if size <= 0:
        return None
    order = client.place_order(
        token_id=signal.token_id,
        side=signal.side,
        price=row["entry_price"],
        size=size,
        strategy_name=strategy.name,
        order_type=order_type,
        market_id=signal.market_id,
        position_metadata={
            "question": row.get("question"),
            "city": row.get("city"),
            "regime": row.get("regime"),
            "setup_type": row.get("setup_type"),
            "take_profit_price": row.get("take_profit_price"),
            "take_profit_partial_price": row.get("take_profit_partial_price"),
            "review_below_price": row.get("review_below_price"),
            "hold_to_expiry": row.get("hold_to_expiry"),
        },
    )
    return {
        "order_id": order.order_id,
        "status": order.status,
        "price": order.price,
        "size": order.size,
        "question": row["question"],
    }


async def watch_entries(
    client: PolymarketClient,
    strategy: WeatherNOAA,
    ranked: List[Dict[str, Any]],
    min_edge: float,
    order_type: str,
    watch_seconds: float,
    execute: bool,
    bankroll: float,
    seen_tokens: Optional[Set[str]] = None,
    recent_fills: Optional[List[Dict[str, Any]]] = None,
    announce: bool = True,
) -> List[Dict[str, Any]]:
    stream = ClobMarketStream()
    by_token = {row["token_id"]: dict(row) for row in ranked}
    fills: List[Dict[str, Any]] = []
    seen = seen_tokens if seen_tokens is not None else set()

    def _on_quote(token_id: str, quote: Dict[str, Optional[float]], _: Dict[str, Any]) -> None:
        row = by_token.get(token_id)
        if row is None or token_id in seen:
            return
        best_ask = quote.get("best_ask")
        if best_ask is None:
            return
        live_edge = row["signal"].estimated_prob - float(best_ask)
        if live_edge < min_edge:
            return
        row["entry_price"] = round(float(best_ask), 4)
        row["live_edge"] = round(live_edge, 4)
        if announce:
            print(
                f"armed token={token_id} edge={live_edge:.4f} ask={float(best_ask):.4f} "
                f"conf={row['signal'].confidence:.2f} | {row['question']}"
            )
        if not execute:
            seen.add(token_id)
            return
        fill = execute_entry(client, strategy, row, bankroll=bankroll, order_type=order_type)
        if fill is None:
            return
        fill["token_id"] = token_id
        fill["live_edge"] = row["live_edge"]
        fill["confidence"] = row["confidence"]
        fill["city"] = row["city"]
        fill["timestamp"] = datetime.now(timezone.utc).isoformat()
        fills.append(fill)
        seen.add(token_id)
        if recent_fills is not None:
            recent_fills.append(fill)
            del recent_fills[:-8]
        if announce:
            print(
                f"filled status={fill['status']} size={fill['size']:.4f} "
                f"price={fill['price']:.4f} | {fill['question']}"
            )

    await stream.stream_quotes(list(by_token.keys()), duration_seconds=watch_seconds, callback=_on_quote)
    return fills


def execute_ranked_rows(
    client: PolymarketClient,
    strategy: WeatherNOAA,
    ranked: List[Dict[str, Any]],
    bankroll: float,
    order_type: str,
    seen_tokens: Set[str],
    recent_fills: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    fills: List[Dict[str, Any]] = []
    for row in ranked:
        token_id = str(row.get("token_id") or "").strip()
        if not token_id or token_id in seen_tokens:
            continue
        fill = execute_entry(client, strategy, row, bankroll=bankroll, order_type=order_type)
        if fill is None:
            continue
        fill["token_id"] = token_id
        fill["live_edge"] = row["live_edge"]
        fill["confidence"] = row["confidence"]
        fill["city"] = row["city"]
        fill["timestamp"] = datetime.now(timezone.utc).isoformat()
        fills.append(fill)
        recent_fills.append(fill)
        del recent_fills[:-8]
        seen_tokens.add(token_id)
        if len(fills) >= max(1, int(limit)):
            break
    return fills


def render_snapshot(
    snapshot: Dict[str, Any],
    top_rows: List[Dict[str, Any]],
    monitor_rows: List[Dict[str, Any]],
    blocked_rows: List[Dict[str, Any]],
    recent_fills: List[Dict[str, Any]],
    cycle: int,
    mode: str,
    execute_enabled: bool,
    catalog_only: bool,
) -> None:
    def _display_time(value: Any) -> str:
        raw = str(value or "").strip()
        if len(raw) >= 19 and "T" in raw:
            return raw[11:19]
        return raw[-8:] if raw else "-"

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(
        f"Weather Monitor | cycle={cycle} | utc={datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} | "
        f"mode={mode} | execute={'on' if execute_enabled else 'off'} | catalog_only={'yes' if catalog_only else 'no'}\n"
    )
    timings = snapshot.get("timings_ms") or {}
    sys.stdout.write(
        f"markets={snapshot.get('market_count', 0)} opps={snapshot.get('opportunity_count', 0)} "
        f"signals={snapshot.get('signal_count', 0)} bettable={len(snapshot.get('ranked') or [])} "
        f"monitor={len(snapshot.get('monitoring') or [])} blocked={len(snapshot.get('blocked') or [])} "
        f"catalog={snapshot.get('catalog_count', '-')} quote_mode={snapshot.get('quote_mode', '-')} "
        f"load_ms={timings.get('load_markets', 0)} prewarm_ms={timings.get('prewarm', 0)} "
        f"analyze_ms={timings.get('analyze', 0)} total_ms={timings.get('total', 0)} "
        f"cities={snapshot.get('prewarm', {}).get('city_count', 0)}\n"
    )
    sys.stdout.write("\nBettable now\n")
    if not top_rows:
        sys.stdout.write("  none\n")
    for idx, row in enumerate(top_rows, start=1):
        sys.stdout.write(
            f"  {idx:02d} edge={row['live_edge']:.4f} conf={row['confidence']:.2f} "
            f"ask={row['best_ask']:.4f} fair={row['estimated_prob']:.4f} "
            f"city={row['city'] or '-':<12} station={row['station_id'] or '-':<6} "
            f"setup={row['setup_type'] or '-':<12} regime={row['regime'] or '-':<14} "
            f"day={row.get('target_date') or '-':<10} left={row.get('time_to_cutoff') or '-':<8} "
            f"tp={float(row.get('take_profit_price') or 0.0):.3f} "
            f"rv={float(row.get('review_below_price') or 0.0):.3f} | {row['question']}\n"
        )
    sys.stdout.write("\nMonitor / wait\n")
    if not monitor_rows:
        sys.stdout.write("  none\n")
    for idx, row in enumerate(monitor_rows, start=1):
        sys.stdout.write(
            f"  {idx:02d} reason={row.get('reason_code') or '-':<28} "
            f"edge={float(row.get('live_edge') or row.get('max_edge') or 0.0):.4f} "
            f"conf={float(row.get('confidence') or 0.0):.2f} "
            f"req={float(row.get('required_edge') or 0.0):.4f} "
            f"day={row.get('target_date') or '-':<10} left={row.get('time_to_cutoff') or '-':<8} "
            f"| {row['question']}\n"
        )
    sys.stdout.write("\nBlocked / no bet\n")
    if not blocked_rows:
        sys.stdout.write("  none\n")
    for idx, row in enumerate(blocked_rows, start=1):
        sys.stdout.write(
            f"  {idx:02d} reason={row.get('reason_code') or '-':<28} "
            f"day={row.get('target_date') or '-':<10} left={row.get('time_to_cutoff') or '-':<8} "
            f"| {row['question']}\n"
        )
    sys.stdout.write("\nRecent fills\n")
    if not recent_fills:
        sys.stdout.write("  none\n")
    for fill in recent_fills[-5:]:
        sys.stdout.write(
            f"  {_display_time(fill.get('timestamp'))} status={fill.get('status')} "
            f"city={fill.get('city') or '-':<12} edge={float(fill.get('live_edge', 0.0)):.4f} "
            f"px={float(fill.get('price', 0.0)):.4f} size={float(fill.get('size', 0.0)):.4f} "
            f"| {fill.get('question')}\n"
        )
    sys.stdout.flush()


def run_loop(args: argparse.Namespace, catalog_rows: Optional[List[Dict[str, Any]]]) -> None:
    client = PolymarketClient(mode=args.mode)
    strategy = WeatherNOAA()
    strategy.set_data_registry(build_registry())
    seen_tokens: Set[str] = set()
    recent_fills: List[Dict[str, Any]] = []
    cycle = 0
    try:
        while True:
            cycle += 1
            snapshot = collect_live_snapshot(
                client=client,
                strategy=strategy,
                max_markets=max(50, args.max_markets),
                page_size=max(50, args.page_size),
                min_edge=max(0.0, args.min_edge),
                min_confidence=max(0.0, args.min_confidence),
                catalog_rows=catalog_rows,
                workers=max(1, args.workers),
            )
            ranked = list(snapshot["ranked"])
            top_rows = ranked[: max(1, args.top)]
            monitor_rows = list(snapshot["monitoring"])[: max(1, args.monitor_top)]
            blocked_rows = list(snapshot["blocked"])[: max(1, args.blocked_top)]

            if args.execute:
                bankroll = client.get_balance() or float(args.bankroll)
                fills = execute_ranked_rows(
                    client=client,
                    strategy=strategy,
                    ranked=top_rows,
                    bankroll=bankroll,
                    order_type=args.order_type,
                    seen_tokens=seen_tokens,
                    recent_fills=recent_fills,
                    limit=max(1, args.max_exec_per_cycle),
                )
                if fills and not args.screen and not args.json:
                    for fill in fills:
                        print(
                            f"filled status={fill['status']} size={fill['size']:.4f} "
                            f"price={fill['price']:.4f} | {fill['question']}"
                        )

            if args.watch_seconds > 0 and ranked:
                bankroll = client.get_balance() or float(args.bankroll)
                watch_rows = [row for row in ranked if row["token_id"] not in seen_tokens][: max(1, args.subscribe_top)]
                if watch_rows:
                    asyncio.run(
                        watch_entries(
                            client=client,
                            strategy=strategy,
                            ranked=watch_rows,
                            min_edge=max(0.0, args.min_edge),
                            order_type=args.order_type,
                            watch_seconds=args.watch_seconds,
                            execute=bool(args.execute),
                            bankroll=bankroll,
                            seen_tokens=seen_tokens,
                            recent_fills=recent_fills,
                            announce=not args.screen,
                        )
                    )

            if args.screen:
                render_snapshot(
                    snapshot=snapshot,
                    top_rows=top_rows,
                    monitor_rows=monitor_rows,
                    blocked_rows=blocked_rows,
                    recent_fills=recent_fills,
                    cycle=cycle,
                    mode=args.mode,
                    execute_enabled=bool(args.execute),
                    catalog_only=bool(catalog_rows is not None),
                )
            elif args.json:
                print(
                    json.dumps(
                        {
                            "cycle": cycle,
                            "market_count": snapshot["market_count"],
                            "signal_count": snapshot["signal_count"],
                            "ranked_entries": len(ranked),
                            "monitoring_entries": len(snapshot["monitoring"]),
                            "blocked_entries": len(snapshot["blocked"]),
                            "timings_ms": snapshot["timings_ms"],
                            "prewarm": snapshot["prewarm"],
                            "top": _json_safe_rows(top_rows),
                            "monitoring": _json_safe_rows(monitor_rows),
                            "blocked": _json_safe_rows(blocked_rows),
                        },
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
            else:
                print(
                    f"cycle={cycle} ranked_entries={len(ranked)} monitor={len(snapshot['monitoring'])} "
                    f"blocked={len(snapshot['blocked'])} total_ms={snapshot['timings_ms']['total']} "
                    f"quote_mode={snapshot['quote_mode']}"
                )

            if args.cycles and cycle >= args.cycles:
                break
            time.sleep(max(0.0, float(args.refresh_seconds)))
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run S02 with live CLOB quotes and optional websocket execution")
    parser.add_argument("--mode", default="paper", choices=["paper", "live"], help="Client mode")
    parser.add_argument("--max-markets", type=int, default=800, help="How many active markets to scan")
    parser.add_argument("--page-size", type=int, default=200, help="Gamma page size")
    parser.add_argument("--top", type=int, default=10, help="How many entries to print")
    parser.add_argument("--monitor-top", type=int, default=5, help="How many monitor entries to print")
    parser.add_argument("--blocked-top", type=int, default=5, help="How many blocked entries to print")
    parser.add_argument("--subscribe-top", type=int, default=5, help="How many top entries to stream over websocket")
    parser.add_argument("--min-edge", type=float, default=0.05, help="Minimum live executable edge")
    parser.add_argument("--min-confidence", type=float, default=0.50, help="Minimum signal confidence")
    parser.add_argument("--watch-seconds", type=float, default=0.0, help="If >0, stream top entries for this long")
    parser.add_argument("--loop", action="store_true", help="Continuously refresh the screen and keep scanning")
    parser.add_argument("--cycles", type=int, default=0, help="When --loop is set, stop after this many cycles (0 = infinite)")
    parser.add_argument("--refresh-seconds", type=float, default=5.0, help="Sleep between loop cycles")
    parser.add_argument("--screen", action="store_true", help="Render a continuously refreshed terminal screen")
    parser.add_argument("--order-type", default="FAK", help="GTC/FAK/FOK when --execute is used")
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Fallback bankroll when live balance is unavailable")
    parser.add_argument("--max-exec-per-cycle", type=int, default=3, help="Maximum fresh fills to place per loop cycle")
    parser.add_argument("--workers", type=int, default=8, help="Parallel strategy-analysis workers")
    parser.add_argument("--catalog-path", default=None, help="Optional weather catalog JSON for city/country/region filtering")
    parser.add_argument("--catalog-only", action="store_true", help="Use only the saved weather catalog instead of rescanning active Gamma markets")
    parser.add_argument("--city", default=None, help="Filter to one canonical city from the saved catalog")
    parser.add_argument("--country", default=None, help="Filter to one country code from the saved catalog")
    parser.add_argument("--region", default=None, help="Filter to one region key from the saved catalog")
    parser.add_argument("--supported-only", action="store_true", help="When using a catalog, keep only provider-supported cities")
    parser.add_argument("--execute", action="store_true", help="Actually place orders")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    if args.catalog_only and not args.catalog_path:
        parser.error("--catalog-only requires --catalog-path")

    catalog_rows = None
    if args.catalog_path and args.catalog_only:
        catalog_rows = load_filtered_catalog_rows(
            args.catalog_path,
            city=args.city,
            country=args.country,
            region=args.region,
            supported_only=bool(args.supported_only),
        )

    if args.loop:
        if not args.screen and sys.stdout.isatty():
            args.screen = True
        run_loop(args, catalog_rows=catalog_rows)
        return

    client = PolymarketClient(mode=args.mode)
    strategy = WeatherNOAA()
    strategy.set_data_registry(build_registry())
    snapshot = collect_live_snapshot(
        client=client,
        strategy=strategy,
        max_markets=max(50, args.max_markets),
        page_size=max(50, args.page_size),
        min_edge=max(0.0, args.min_edge),
        min_confidence=max(0.0, args.min_confidence),
        catalog_rows=catalog_rows,
        workers=max(1, args.workers),
    )
    ranked = list(snapshot["ranked"])
    top_rows = ranked[: max(1, args.top)]
    monitor_rows = list(snapshot["monitoring"])[: max(1, args.monitor_top)]
    blocked_rows = list(snapshot["blocked"])[: max(1, args.blocked_top)]

    if args.json:
        print(
            json.dumps(
                {
                    "market_count": snapshot["market_count"],
                    "opportunity_count": snapshot["opportunity_count"],
                    "signal_count": snapshot["signal_count"],
                    "ranked_entries": len(ranked),
                    "monitoring_entries": len(snapshot["monitoring"]),
                    "blocked_entries": len(snapshot["blocked"]),
                    "timings_ms": snapshot["timings_ms"],
                    "quote_mode": snapshot["quote_mode"],
                    "top": _json_safe_rows(top_rows),
                    "monitoring": _json_safe_rows(monitor_rows),
                    "blocked": _json_safe_rows(blocked_rows),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(
            f"ranked_entries={len(ranked)} markets={snapshot['market_count']} "
            f"opps={snapshot['opportunity_count']} signals={snapshot['signal_count']} "
            f"monitor={len(snapshot['monitoring'])} blocked={len(snapshot['blocked'])} "
            f"total_ms={snapshot['timings_ms']['total']} quote_mode={snapshot['quote_mode']}"
        )
        for idx, row in enumerate(top_rows, start=1):
            print(
                f"{idx:02d} edge={row['live_edge']:.4f} conf={row['confidence']:.2f} "
                f"ask={row['best_ask']:.4f} fair={row['estimated_prob']:.4f} "
                f"city={row['city'] or '-':<12} station={row['station_id'] or '-':<6} "
                f"settle={row['settlement_source'] or '-':<18} loc={row['settlement_location_id'] or '-':<4} "
                f"setup={row['setup_type'] or '-':<14} regime={row['regime'] or '-':<14} "
                f"day={row.get('target_date') or '-':<10} left={row.get('time_to_cutoff') or '-':<8} "
                f"tp={float(row.get('take_profit_price') or 0.0):.3f} "
                f"rv={float(row.get('review_below_price') or 0.0):.3f} "
                f"budget=${row['budget_cap_usd']:.2f} | {row['question']}"
            )
        if monitor_rows:
            print("monitor:")
            for idx, row in enumerate(monitor_rows, start=1):
                print(
                    f"m{idx:02d} reason={row.get('reason_code') or '-'} "
                    f"edge={float(row.get('live_edge') or row.get('max_edge') or 0.0):.4f} "
                    f"conf={float(row.get('confidence') or 0.0):.2f} "
                    f"req={float(row.get('required_edge') or 0.0):.4f} | {row['question']}"
                )
        if blocked_rows:
            print("blocked:")
            for idx, row in enumerate(blocked_rows, start=1):
                print(f"b{idx:02d} reason={row.get('reason_code') or '-'} | {row['question']}")

    if args.execute and args.watch_seconds <= 0:
        bankroll = client.get_balance() or float(args.bankroll)
        seen_tokens: Set[str] = set()
        recent_fills: List[Dict[str, Any]] = []
        fills = execute_ranked_rows(
            client=client,
            strategy=strategy,
            ranked=top_rows,
            bankroll=bankroll,
            order_type=args.order_type,
            seen_tokens=seen_tokens,
            recent_fills=recent_fills,
            limit=max(1, args.max_exec_per_cycle),
        )
        for fill in fills:
            print(
                f"filled status={fill['status']} size={fill['size']:.4f} "
                f"price={fill['price']:.4f} | {fill['question']}"
            )

    if args.watch_seconds > 0:
        watch_rows = ranked[: max(1, args.subscribe_top)]
        fills = asyncio.run(
            watch_entries(
                client=client,
                strategy=strategy,
                ranked=watch_rows,
                min_edge=max(0.0, args.min_edge),
                order_type=args.order_type,
                watch_seconds=args.watch_seconds,
                execute=bool(args.execute),
                bankroll=(client.get_balance() or float(args.bankroll)),
                announce=True,
            )
        )
        if args.json and fills:
            print(json.dumps({"fills": fills}, ensure_ascii=False, indent=2))

    client.close()


if __name__ == "__main__":
    main()
