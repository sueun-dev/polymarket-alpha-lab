#!/usr/bin/env python3
"""Scan live Polymarket weather markets and print the best S02 setups."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.client import PolymarketClient
from data import DataRegistry
from data.aviationweather import AviationWeatherProvider
from data.global_climate import GlobalClimateProvider
from data.nws_climate import NWSClimateProvider
from data.weather_router import WeatherRouterProvider
from strategies.tier_s.s02_weather_noaa import WeatherNOAA


def build_registry() -> DataRegistry:
    registry = DataRegistry()
    registry.register(WeatherRouterProvider())
    registry.register(AviationWeatherProvider())
    registry.register(NWSClimateProvider())
    registry.register(GlobalClimateProvider())
    return registry


def rank_signals(limit: int) -> list[dict[str, Any]]:
    client = PolymarketClient(mode="paper")
    strategy = WeatherNOAA()
    strategy.set_data_registry(build_registry())

    markets = client.get_markets(limit=limit, active_only=True, order_by="volume", ascending=False)
    rows: list[dict[str, Any]] = []
    for opp in strategy.scan(markets):
        signal = strategy.analyze(opp)
        if signal is None:
            continue
        rows.append(
            {
                "market_id": opp.market_id,
                "question": opp.question,
                "side": signal.metadata.get("side_selected", "yes"),
                "market_price": round(signal.market_price, 4),
                "fair_yes_prob": round(float(signal.metadata.get("fair_yes_prob", 0.0)), 4),
                "edge": round(float(signal.metadata.get("edge", 0.0)), 4),
                "confidence": round(signal.confidence, 4),
                "city": signal.metadata.get("city"),
                "station_id": signal.metadata.get("station_id"),
                "setup_type": signal.metadata.get("setup_type"),
                "regime": signal.metadata.get("regime"),
                "hold_to_expiry": bool(signal.metadata.get("hold_to_expiry")),
                "take_profit_price": round(float(signal.metadata.get("take_profit_price", signal.market_price)), 4),
                "review_below_price": round(float(signal.metadata.get("review_below_price", signal.market_price)), 4),
                "budget_cap_usd": round(float(signal.metadata.get("budget_cap_usd", 0.0)), 2),
            }
        )
    rows.sort(key=lambda row: (row["edge"] * row["confidence"], row["edge"]), reverse=True)
    client.close()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank live weather setups for the S02 strategy")
    parser.add_argument("--limit", type=int, default=300, help="How many active Polymarket markets to scan")
    parser.add_argument("--top", type=int, default=20, help="How many ranked setups to print")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a plain-text table")
    args = parser.parse_args()

    rows = rank_signals(limit=max(10, args.limit))
    top_rows = rows[: max(1, args.top)]

    if args.json:
        print(json.dumps(top_rows, ensure_ascii=False, indent=2))
        return

    print(f"ranked_setups={len(rows)}")
    for idx, row in enumerate(top_rows, start=1):
        print(
            f"{idx:02d} side={row['side']:<3} edge={row['edge']:.3f} conf={row['confidence']:.2f} "
            f"px={row['market_price']:.3f} fair={row['fair_yes_prob']:.3f} "
            f"city={row['city'] or '-':<12} station={row['station_id'] or '-':<6} "
            f"setup={row['setup_type']:<12} regime={row['regime'] or '-':<14} "
            f"tp={row['take_profit_price']:.3f} rv={row['review_below_price']:.3f} "
            f"budget=${row['budget_cap_usd']:.2f} | {row['question']}"
        )


if __name__ == "__main__":
    main()
