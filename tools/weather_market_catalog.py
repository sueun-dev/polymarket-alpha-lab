#!/usr/bin/env python3
"""Discover all active weather markets and persist a city/region catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.client import PolymarketClient
from core.weather_catalog import discover_weather_markets, save_catalog, summarize_catalog
from data import DataRegistry
from data.aviationweather import AviationWeatherProvider
from data.global_climate import GlobalClimateProvider
from data.nws_climate import NWSClimateProvider
from data.weather_router import WeatherRouterProvider
from strategies.tier_s.s02_weather_noaa import WeatherNOAA


def build_engine():
    strategy = WeatherNOAA()
    registry = DataRegistry()
    weather = WeatherRouterProvider()
    registry.register(weather)
    registry.register(AviationWeatherProvider())
    registry.register(NWSClimateProvider())
    registry.register(GlobalClimateProvider())
    strategy.set_data_registry(registry)
    return strategy._engine(weather)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a live catalog of active weather markets")
    parser.add_argument("--max-markets", type=int, default=5000, help="How many active markets to scan")
    parser.add_argument("--page-size", type=int, default=200, help="Gamma page size")
    parser.add_argument("--out", default="logs/weather_market_catalog.json", help="Output JSON path")
    parser.add_argument("--json", action="store_true", help="Print the full catalog JSON to stdout")
    args = parser.parse_args()

    client = PolymarketClient(mode="paper")
    rows = discover_weather_markets(
        client=client,
        engine=build_engine(),
        max_markets=max(100, args.max_markets),
        page_size=max(50, args.page_size),
    )
    client.close()

    out_path = Path(args.out)
    save_catalog(out_path, rows)
    summary = summarize_catalog(rows)

    if args.json:
        print(json.dumps({"summary": summary, "markets": rows}, ensure_ascii=False, indent=2))
        return

    print(f"saved={out_path}")
    print(f"weather_markets={summary['count']}")
    print(f"provider_supported={summary['provider_supported_count']}")
    print("countries")
    for country, count in list(summary["countries"].items())[:12]:
        print(f"  {country}: {count}")
    print("cities")
    for city, count in list(summary["cities"].items())[:20]:
        print(f"  {city}: {count}")


if __name__ == "__main__":
    main()
