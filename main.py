# main.py
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.scanner import MarketScanner
from data import DataRegistry
from data.polymarket import PolymarketMarketDataClient
from strategies import StrategyRegistry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("polymarket-strategy-lab")


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def init_data_registry() -> DataRegistry:
    """Initialize read-only data providers for strategy analysis."""
    from data.base_rates import BaseRateProvider
    from data.feature_engine import LiveFeatureBuilder
    from data.historical_fetcher import HistoricalFetcher
    from data.kalshi_client import KalshiDataProvider
    from data.news_client import NewsDataProvider
    from data.noaa import NOAAWeatherProvider

    registry = DataRegistry()
    providers = [
        HistoricalFetcher(),
        LiveFeatureBuilder(),
        BaseRateProvider(),
        NOAAWeatherProvider(),
        KalshiDataProvider(),
        NewsDataProvider(),
    ]

    for provider in providers:
        registry.register(provider)
        logger.info("Registered data provider: %s", provider.name)

    return registry


def load_strategies(strategy_filter: str | None = None, attach_data: bool = True):
    registry = StrategyRegistry()
    registry.discover()
    strategies = registry.get_all()
    if strategy_filter:
        strategies = [s for s in strategies if strategy_filter in s.name]

    if attach_data:
        data_registry = init_data_registry()
        for strategy in strategies:
            strategy.set_data_registry(data_registry)
    return strategies


def run_list(_: dict) -> None:
    strategies = load_strategies(attach_data=False)
    if not strategies:
        print("No strategies found. Add strategy modules to strategies/tier_*/")
        return

    print(f"\n{'#':<5} {'Name':<40} {'Tier':<6} {'Data'}")
    print("-" * 70)
    for strategy in sorted(strategies, key=lambda x: x.strategy_id):
        data = ", ".join(strategy.required_data) if strategy.required_data else "-"
        print(f"{strategy.strategy_id:<5} {strategy.name:<40} {strategy.tier:<6} {data}")
    print(f"\nTotal: {len(strategies)} strategies")


def run_scan(
    config: dict,
    strategy_filter: str | None = None,
    limit: int = 20,
) -> None:
    """Run a one-shot read-only scan and print strategy signals."""
    scan_cfg = config.get("scanner", {})
    signal_cfg = config.get("signals", {})
    min_edge = float(signal_cfg.get("min_edge", 0.05))

    client = PolymarketMarketDataClient()
    scanner = MarketScanner(
        client=client,
        min_volume=scan_cfg.get("min_volume", 1000),
        min_liquidity=scan_cfg.get("min_liquidity", 0),
        categories=scan_cfg.get("categories", []),
    )
    strategies = load_strategies(strategy_filter)

    if not strategies:
        print("No strategies found.")
        return

    markets = scanner.scan(limit=scan_cfg.get("max_markets", 100))
    rows = []
    for strategy in strategies:
        try:
            opportunities = strategy.scan(markets)
        except Exception as exc:
            logger.warning("%s scan failed: %s", strategy.name, exc)
            continue

        for opportunity in opportunities:
            try:
                signal = strategy.analyze(opportunity)
            except Exception as exc:
                logger.warning("%s analyze failed: %s", strategy.name, exc)
                continue
            if signal is None or signal.edge < min_edge:
                continue
            rows.append((signal.edge, strategy.name, opportunity.question, signal.side, signal.market_price, signal.estimated_prob))

    rows.sort(reverse=True, key=lambda row: row[0])
    rows = rows[:limit]

    if not rows:
        print("No strategy signals found at the current thresholds.")
        return

    print(f"\n{'Edge':<8} {'Strategy':<34} {'Side':<6} {'Price':<8} {'Est. Prob':<10} Question")
    print("-" * 120)
    for edge, strategy_name, question, side, price, estimated_prob in rows:
        print(f"{edge:<8.3f} {strategy_name:<34} {side:<6} {price:<8.3f} {estimated_prob:<10.3f} {question[:72]}")


def run_backtest(config: dict, strategy_filter: str | None = None, data_dir: str = "data/historical/") -> None:
    from backtest.data_loader import DataLoader
    from backtest.engine import BacktestEngine
    from backtest.report import BacktestReport

    strategies = load_strategies(strategy_filter)
    if not strategies:
        print("No strategies found.")
        return

    loader = DataLoader()
    data_path = Path(data_dir)

    all_data = []
    if data_path.exists():
        for f in data_path.iterdir():
            if f.suffix == ".csv":
                all_data.extend(loader.load_csv(str(f)))
            elif f.suffix == ".json":
                all_data.extend(loader.load_json(str(f)))

    if not all_data:
        print(f"No historical data found in {data_dir}")
        print("Expected CSV format: timestamp,condition_id,question,yes_price,no_price,volume")
        print("Place .csv or .json files in data/historical/ and try again.")
        return

    initial = config.get("backtest", {}).get("initial_balance", 10000.0)
    slippage = config.get("backtest", {}).get("slippage", 0.005)

    for strategy in sorted(strategies, key=lambda x: x.strategy_id):
        engine = BacktestEngine(strategy=strategy, initial_balance=initial, slippage=slippage)
        result = engine.run(all_data)
        report = BacktestReport(result)
        print(f"\n--- {strategy.name} (#{strategy.strategy_id}, Tier {strategy.tier}) ---")
        print(report.to_text())


def run_collect_data(config: dict) -> None:
    """Fetch historical market data for research/backtesting."""
    from data.historical_fetcher import HistoricalFetcher

    fetcher = HistoricalFetcher()
    max_markets = config.get("data", {}).get("max_markets", 500)

    print(f"Fetching up to {max_markets} historical markets...")
    markets = fetcher.fetch_closed_binary_markets(max_markets=max_markets)
    print(f"Fetched {len(markets)} resolved binary markets")

    if markets:
        categories: dict[str, int] = {}
        for market in markets:
            categories[market.category] = categories.get(market.category, 0) + 1
        print("\nCategories:")
        for category, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {category}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket Alpha Lab Strategy Research CLI")
    parser.add_argument("command", nargs="?", default="list", choices=["list", "scan", "backtest", "collect-data"], help="Command to execute")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--strategy", default=None, help="Filter to a specific strategy name")
    parser.add_argument("--data-dir", default="data/historical/", help="Historical data directory for backtests")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to print for scan")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.command == "list":
        run_list(config)
    elif args.command == "scan":
        run_scan(config, strategy_filter=args.strategy, limit=args.limit)
    elif args.command == "backtest":
        run_backtest(config, strategy_filter=args.strategy, data_dir=args.data_dir)
    elif args.command == "collect-data":
        run_collect_data(config)


if __name__ == "__main__":
    main()
