# main.py
from __future__ import annotations

import argparse
import logging
import time
import yaml
from pathlib import Path
from dotenv import load_dotenv

from core.client import PolymarketClient
from core.risk import RiskManager
from core.kelly import KellyCriterion
from core.scanner import MarketScanner
from core.notifier import Notifier
from core.base_strategy import BaseStrategy
from strategies import StrategyRegistry
from data import DataRegistry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("polymarket-bot")


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def init_data_registry() -> DataRegistry:
    """Initialize all data providers and return a populated registry."""
    from data.historical_fetcher import HistoricalFetcher
    from data.feature_engine import LiveFeatureBuilder
    from data.base_rates import BaseRateProvider
    from data.noaa import NOAAWeatherProvider
    from data.kalshi_client import KalshiDataProvider
    from data.news_client import NewsDataProvider

    registry = DataRegistry()

    providers = [
        HistoricalFetcher(),
        LiveFeatureBuilder(),
        BaseRateProvider(),
        NOAAWeatherProvider(),
        KalshiDataProvider(),
        NewsDataProvider(),
    ]

    for p in providers:
        registry.register(p)
        logger.info(f"Registered data provider: {p.name}")

    return registry


def run_bot(config: dict, strategy_filter: str | None = None, dry_run: bool = False):
    bot_cfg = config.get("bot", {})
    risk_cfg = config.get("risk", {})
    scan_cfg = config.get("scanner", {})
    notif_cfg = config.get("notifications", {})

    mode = "paper" if dry_run else bot_cfg.get("mode", "paper")
    scan_interval = bot_cfg.get("scan_interval", 60)

    client = PolymarketClient(mode=mode)
    risk = RiskManager(
        max_position_pct=risk_cfg.get("max_position_pct", 0.10),
        max_daily_loss_pct=risk_cfg.get("max_daily_loss_pct", 0.05),
        max_open_positions=risk_cfg.get("max_open_positions", 20),
        min_edge=risk_cfg.get("min_edge", 0.05),
    )
    scanner = MarketScanner(
        client=client,
        min_volume=scan_cfg.get("min_volume", 1000),
        min_liquidity=scan_cfg.get("min_liquidity", 0),
        categories=scan_cfg.get("categories", []),
    )
    notifier = Notifier(
        telegram_enabled=notif_cfg.get("telegram", False),
        discord_enabled=notif_cfg.get("discord", False),
    )

    # Discover and register strategies
    registry = StrategyRegistry()
    registry.discover()

    strategies = registry.get_all()
    if strategy_filter:
        strategies = [s for s in strategies if strategy_filter in s.name]

    logger.info(f"Bot starting | Mode: {mode} | Strategies: {len(strategies)} | Interval: {scan_interval}s")

    if not strategies:
        logger.warning("No strategies loaded. Add strategy modules to strategies/tier_*/")
        return

    # Initialize data providers
    data_registry = init_data_registry()
    for strategy in strategies:
        strategy.set_data_registry(data_registry)
    logger.info(f"Data providers: {len(data_registry)} registered")

    # Main loop
    try:
        while True:
            try:
                bankroll = client.get_balance()
                positions = client.get_positions()
                markets = scanner.scan()
                logger.info(f"Scanned {len(markets)} markets | Balance: ${bankroll:.2f}")

                for strategy in strategies:
                    try:
                        opportunities = strategy.scan(markets)
                        for opp in opportunities:
                            signal = strategy.analyze(opp)
                            if signal is None:
                                continue
                            if not risk.can_trade(signal, bankroll=bankroll, current_positions=[]):
                                continue
                            size = strategy.size_position(signal, bankroll=bankroll)
                            if size <= 0:
                                continue
                            order = strategy.execute(signal, size, client=client)
                            if order:
                                notifier.trade_alert(
                                    strategy=strategy.name,
                                    side=order.side,
                                    market=signal.market_id,
                                    price=order.price,
                                    size=order.size,
                                )
                                logger.info(f"[{strategy.name}] Order: {order.side} {order.size}x @ {order.price}")
                    except Exception as e:
                        logger.error(f"Strategy {strategy.name} error: {e}")
                        notifier.error_alert(f"{strategy.name}: {e}")

            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                notifier.error_alert(str(e))

            time.sleep(scan_interval)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


def run_list(config: dict):
    registry = StrategyRegistry()
    registry.discover()
    strategies = registry.get_all()
    if not strategies:
        print("No strategies found. Add modules to strategies/tier_*/")
        return
    print(f"\n{'#':<5} {'Name':<40} {'Tier':<6} {'Data'}")
    print("-" * 70)
    for s in sorted(strategies, key=lambda x: x.strategy_id):
        data = ", ".join(s.required_data) if s.required_data else "-"
        print(f"{s.strategy_id:<5} {s.name:<40} {s.tier:<6} {data}")
    print(f"\nTotal: {len(strategies)} strategies")


def run_backtest(config: dict, strategy_filter: str | None = None, data_dir: str = "data/historical/"):
    from backtest.data_loader import DataLoader
    from backtest.engine import BacktestEngine
    from backtest.report import BacktestReport

    registry = StrategyRegistry()
    registry.discover()

    strategies = registry.get_all()
    if strategy_filter:
        strategies = [s for s in strategies if strategy_filter in s.name]

    if not strategies:
        print("No strategies found.")
        return

    loader = DataLoader()
    data_path = Path(data_dir)

    # Load all CSV/JSON files from data directory
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


def run_collect_data(config: dict):
    """Fetch historical market data for backtesting and analysis."""
    from data.historical_fetcher import HistoricalFetcher

    fetcher = HistoricalFetcher()
    max_markets = config.get("data", {}).get("max_markets", 500)

    print(f"Fetching up to {max_markets} historical markets...")
    markets = fetcher.fetch_closed_binary_markets(max_markets=max_markets)
    print(f"Fetched {len(markets)} resolved binary markets")

    if markets:
        categories: dict[str, int] = {}
        for m in markets:
            categories[m.category] = categories.get(m.category, 0) + 1
        print("\nCategories:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Polymarket Alpha Lab Trading Bot")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "list", "backtest", "collect-data"], help="Command to execute")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--strategy", default=None, help="Filter to specific strategy name")
    parser.add_argument("--dry-run", action="store_true", help="Run in paper mode regardless of config")
    parser.add_argument("--data-dir", default="data/historical/", help="Historical data directory for backtests")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.command == "list":
        run_list(config)
    elif args.command == "run":
        run_bot(config, strategy_filter=args.strategy, dry_run=args.dry_run)
    elif args.command == "backtest":
        run_backtest(config, strategy_filter=args.strategy, data_dir=args.data_dir)
    elif args.command == "collect-data":
        run_collect_data(config)


if __name__ == "__main__":
    main()
