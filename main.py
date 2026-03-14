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


def init_data_registry(config: dict | None = None) -> DataRegistry:
    """Initialize all data providers and return a populated registry."""
    from data.historical_fetcher import HistoricalFetcher
    from data.feature_engine import LiveFeatureBuilder
    from data.ai_judge import AIJudgeProvider
    from data.base_rates import BaseRateProvider
    from data.aviationweather import AviationWeatherProvider
    from data.global_climate import GlobalClimateProvider
    from data.nws_climate import NWSClimateProvider
    from data.weather_router import WeatherRouterProvider
    from data.kalshi_client import KalshiDataProvider
    from data.news_client import NewsDataProvider

    cfg = config or {}
    registry = DataRegistry()

    providers = [
        HistoricalFetcher(),
        LiveFeatureBuilder(),
        AIJudgeProvider(cfg.get("ai_judge")),
        BaseRateProvider(),
        WeatherRouterProvider(),
        AviationWeatherProvider(),
        NWSClimateProvider(),
        GlobalClimateProvider(),
        KalshiDataProvider(),
        NewsDataProvider(),
    ]

    for p in providers:
        registry.register(p)
        logger.info(f"Registered data provider: {p.name}")

    return registry


def apply_strategy_runtime_config(strategies: list[BaseStrategy], config: dict) -> None:
    """Apply runtime sizing controls from config onto instantiated strategies."""
    risk_cfg = config.get("risk", {}) if isinstance(config, dict) else {}
    raw_fraction = risk_cfg.get("kelly_fraction")
    try:
        kelly_fraction = float(raw_fraction)
    except (TypeError, ValueError):
        kelly_fraction = None

    for strategy in strategies:
        if kelly_fraction is not None and hasattr(strategy, "kelly"):
            strategy.kelly.fraction = max(0.0, min(1.0, kelly_fraction))


def run_bot_cycle(
    client: PolymarketClient,
    risk: RiskManager,
    scanner: MarketScanner,
    notifier: Notifier,
    strategies: list[BaseStrategy],
    scan_limit: int = 100,
) -> dict:
    bankroll = client.get_balance()
    positions = client.get_positions()
    markets = scanner.scan(limit=max(1, int(scan_limit)))
    logger.info(f"Scanned {len(markets)} markets | Balance: ${bankroll:.2f}")

    summary = {
        "market_count": len(markets),
        "strategy_count": len(strategies),
        "signals": 0,
        "orders": 0,
        "manuals": 0,
        "errors": 0,
    }

    for strategy in strategies:
        try:
            opportunities = strategy.scan(markets)
            for opp in opportunities:
                signal = strategy.analyze(opp)
                if signal is None:
                    continue
                summary["signals"] += 1
                if not risk.can_trade(signal, bankroll=bankroll, current_positions=positions):
                    continue
                size = strategy.size_position(signal, bankroll=bankroll)
                manual_instruction = build_manual_instruction(
                    strategy,
                    signal,
                    client=client,
                    size=size if size > 0 else None,
                )
                if size <= 0:
                    if manual_instruction:
                        summary["manuals"] += 1
                        notifier.manual_trade_alert(strategy.name, opp.question, manual_instruction)
                        logger.info(f"[{strategy.name}] Manual: {manual_instruction}")
                    continue
                order = strategy.execute(signal, size, client=client)
                if order:
                    summary["orders"] += 1
                    notifier.trade_alert(
                        strategy=strategy.name,
                        side=order.side,
                        market=signal.market_id,
                        price=order.price,
                        size=order.size,
                    )
                    logger.info(f"[{strategy.name}] Order: {order.side} {order.size}x @ {order.price}")
                elif manual_instruction:
                    summary["manuals"] += 1
                    notifier.manual_trade_alert(strategy.name, opp.question, manual_instruction)
                    logger.info(f"[{strategy.name}] Manual: {manual_instruction}")
        except Exception as e:
            summary["errors"] += 1
            logger.error(f"Strategy {strategy.name} error: {e}")
            notifier.error_alert(f"{strategy.name}: {e}")
    return summary


def build_manual_instruction(
    strategy: BaseStrategy,
    signal,
    client=None,
    size: float | None = None,
) -> str | None:
    plan = strategy.build_manual_plan(signal, client=client, size=size)
    if not isinstance(plan, dict):
        return None

    instruction = str(plan.get("instruction_kr", "")).strip()
    if not instruction:
        return None

    status = str(plan.get("status", "manual")).strip()
    limit_price = plan.get("recommended_limit_no_price", plan.get("suggested_limit_no_price"))
    return (
        f"[{status}] "
        f"NO limit <= {limit_price} | {instruction}"
    )


def run_bot(
    config: dict,
    strategy_filter: str | None = None,
    dry_run: bool = False,
    once: bool = False,
    scan_limit: int | None = None,
):
    bot_cfg = config.get("bot", {})
    risk_cfg = config.get("risk", {})
    scan_cfg = config.get("scanner", {})
    notif_cfg = config.get("notifications", {})

    mode = "paper" if dry_run else bot_cfg.get("mode", "paper")
    scan_interval = bot_cfg.get("scan_interval", 60)
    effective_scan_limit = max(1, int(scan_limit or scan_cfg.get("scan_limit", 100)))

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
    data_registry = init_data_registry(config)
    for strategy in strategies:
        strategy.set_data_registry(data_registry)
    apply_strategy_runtime_config(strategies, config)
    logger.info(f"Data providers: {len(data_registry)} registered")

    # Main loop
    try:
        while True:
            try:
                summary = run_bot_cycle(
                    client=client,
                    risk=risk,
                    scanner=scanner,
                    notifier=notifier,
                    strategies=strategies,
                    scan_limit=effective_scan_limit,
                )
                logger.info(
                    "Cycle summary | markets=%s signals=%s orders=%s manuals=%s errors=%s",
                    summary["market_count"],
                    summary["signals"],
                    summary["orders"],
                    summary["manuals"],
                    summary["errors"],
                )

            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                notifier.error_alert(str(e))

            if once:
                break
            time.sleep(scan_interval)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        client.close()


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
    parser.add_argument("--once", action="store_true", help="Run exactly one scan/trade cycle and exit")
    parser.add_argument("--scan-limit", type=int, default=None, help="Maximum active markets to fetch per cycle")
    parser.add_argument("--data-dir", default="data/historical/", help="Historical data directory for backtests")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.command == "list":
        run_list(config)
    elif args.command == "run":
        run_bot(
            config,
            strategy_filter=args.strategy,
            dry_run=args.dry_run,
            once=bool(args.once),
            scan_limit=args.scan_limit,
        )
    elif args.command == "backtest":
        run_backtest(config, strategy_filter=args.strategy, data_dir=args.data_dir)
    elif args.command == "collect-data":
        run_collect_data(config)


if __name__ == "__main__":
    main()
