"""Live API server for the React dashboard.

Serves real-time data sourced from Polymarket endpoints and local strategy code.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from aiohttp import web

from backtest.data_loader import HistoricalDataPoint
from backtest.engine import BacktestEngine
from backtest.report import BacktestReport
from core.client import PolymarketClient
from core.models import Market
from data import DataRegistry
from data.ai_judge import AIJudgeProvider
from data.base_rates import BaseRateProvider
from data.feature_engine import LiveFeatureBuilder
from data.historical_fetcher import HistoricalFetcher
from data.kalshi_client import KalshiDataProvider
from data.news_client import NewsDataProvider
from data.aviationweather import AviationWeatherProvider
from data.global_climate import GlobalClimateProvider
from data.nws_climate import NWSClimateProvider
from data.weather_router import WeatherRouterProvider
from strategies import StrategyRegistry

logger = logging.getLogger("dashboard_api")

# Known KR names. Falls back to EN title when missing.
KR_NAMES: dict[str, str] = {
    "s01_reversing_stupidity": "바보 반대편 베팅",
    "s02_weather_noaa": "날씨 NOAA 차익거래",
    "s03_nothing_ever_happens": "아무 일도 안 일어난다",
    "s04_cross_platform_arb": "크로스플랫폼 차익거래",
    "s05_negrisk_rebalancing": "NegRisk 리밸런싱",
    "s06_btc_latency_arb": "BTC 레이턴시 차익거래 (비활성화)",
    "s07_settlement_rules": "정산 규칙 분석",
    "s08_domain_specialization": "도메인 전문화",
    "s09_oracle_latency": "오라클 레이턴시",
    "s10_yes_bias": "YES 편향 착취",
    "s12_high_prob_harvesting": "고확률 수확",
    "s15_news_mean_reversion": "뉴스 평균회귀",
    "s39_volume_momentum": "거래량 모멘텀",
    "s49_stablecoin_yield": "스테이블코인 수익 비교",
}

CORE_SCANNER_STRATEGIES = [
    "s01_reversing_stupidity",
    "s02_weather_noaa",
    "s03_nothing_ever_happens",
    "s10_yes_bias",
    "s12_high_prob_harvesting",
    "s15_news_mean_reversion",
    "s39_volume_momentum",
    "s49_stablecoin_yield",
]


class Runtime:
    def __init__(self) -> None:
        self.client = PolymarketClient(mode="paper")
        self.data_registry = self._init_data_registry()
        self.strategy_registry = StrategyRegistry()
        self.strategy_registry.discover()
        for strategy in self.strategy_registry.get_all():
            strategy.set_data_registry(self.data_registry)

    @staticmethod
    def _init_data_registry() -> DataRegistry:
        registry = DataRegistry()
        providers = [
            HistoricalFetcher(),
            LiveFeatureBuilder(),
            AIJudgeProvider(),
            BaseRateProvider(),
            WeatherRouterProvider(),
            AviationWeatherProvider(),
            NWSClimateProvider(),
            GlobalClimateProvider(),
            KalshiDataProvider(),
            NewsDataProvider(),
        ]
        for provider in providers:
            registry.register(provider)
        return registry


def parse_price(value: Any) -> Optional[float]:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price < 0 or price > 1:
        return None
    return price


def yes_no_prices(market: Market) -> Tuple[Optional[float], Optional[float]]:
    yes_price = None
    no_price = None
    for token in market.tokens:
        outcome = str(token.get("outcome", "")).strip().lower()
        price = parse_price(token.get("price"))
        if price is None:
            continue
        if outcome == "yes":
            yes_price = price
        elif outcome == "no":
            no_price = price
    if yes_price is not None and no_price is None:
        no_price = 1 - yes_price
    if no_price is not None and yes_price is None:
        yes_price = 1 - no_price
    return yes_price, no_price


def strategy_title_en(strategy_id: str) -> str:
    _, _, tail = strategy_id.partition("_")
    words = tail.split("_") if tail else [strategy_id]
    acronym = {"btc": "BTC", "noaa": "NOAA", "ai": "AI", "ml": "ML", "hft": "HFT", "sdk": "SDK", "sql": "SQL"}
    out = []
    for word in words:
        key = word.lower()
        out.append(acronym.get(key, word.capitalize()))
    return " ".join(out)


def _strategy_number(strategy_id: str) -> int:
    prefix = strategy_id.split("_", 1)[0]
    match = re.match(r"^s(\d+)$", prefix)
    if not match:
        return 0
    return int(match.group(1))


def _clean_doc(doc: str) -> str:
    lines = [line.strip() for line in (doc or "").splitlines()]
    lines = [line for line in lines if line]
    return " ".join(lines)


def _extract_method_doc(class_node: ast.ClassDef, method_name: str) -> str:
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == method_name:
            return _clean_doc(ast.get_docstring(item) or "")
    return ""


def _safe_literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _extract_key_params(class_node: ast.ClassDef) -> list[dict[str, str]]:
    ignore = {"name", "tier", "strategy_id", "required_data"}
    params: list[dict[str, str]] = []
    for item in class_node.body:
        if not isinstance(item, ast.Assign):
            continue
        if len(item.targets) != 1 or not isinstance(item.targets[0], ast.Name):
            continue
        key = item.targets[0].id
        if not key.isupper() or key in ignore:
            continue

        parsed = _safe_literal(item.value)
        if parsed is not None:
            value_str = str(parsed)
        else:
            try:
                value_str = ast.unparse(item.value)
            except Exception:
                value_str = "<expr>"
        params.append({"name": key, "value": value_str})
    return params


def _clean_multiline(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    return "\n".join([line for line in lines if line and line != "---"]).strip()


def _parse_md_fields(section: str) -> dict[str, str]:
    """Parse markdown fields in the form '**필드명:** 값 ...'."""
    fields: dict[str, str] = {}
    pattern = re.compile(r"^\*\*([^*]+?):\*\*\s*(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(section))
    for index, match in enumerate(matches):
        key = match.group(1).strip()
        first_line = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        tail = section[start:end].strip()
        if first_line and tail:
            value = f"{first_line}\n{tail}"
        else:
            value = first_line or tail
        fields[key] = _clean_multiline(value)
    return fields


def load_kr_strategy_details(repo_root: Path) -> dict[int, dict[str, str]]:
    """Load KR strategy descriptions from the research document."""
    candidates = [
        repo_root / "research" / "KR-polymarket-top-100-strategies.md",
        repo_root / "KR-polymarket-top-100-strategies.md",  # legacy fallback
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return {}

    text = path.read_text(encoding="utf-8")
    heading_pattern = re.compile(r"^##\s+(\d+)\.\s+(.+)$", re.MULTILINE)
    headings = list(heading_pattern.finditer(text))

    details: dict[int, dict[str, str]] = {}
    for index, heading in enumerate(headings):
        number = int(heading.group(1))
        title = _clean_multiline(heading.group(2))
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[start:end]

        fields = _parse_md_fields(section)
        overview_kr = fields.get("전략 설명") or title
        scan_logic_kr = fields.get("실행 방법") or ""

        edge = fields.get("예상 엣지", "")
        risk = fields.get("핵심 리스크", "")
        if edge and risk:
            analyze_logic_kr = f"예상 엣지: {edge}\n핵심 리스크: {risk}"
        elif edge:
            analyze_logic_kr = f"예상 엣지: {edge}"
        elif risk:
            analyze_logic_kr = f"핵심 리스크: {risk}"
        else:
            analyze_logic_kr = ""

        details[number] = {
            "overviewKr": overview_kr,
            "scanLogicKr": scan_logic_kr,
            "analyzeLogicKr": analyze_logic_kr,
        }

    return details


def load_strategy_catalog(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    kr_details = load_kr_strategy_details(repo_root)
    for path in sorted((repo_root / "strategies").glob("tier_*/s*.py")):
        strategy_id = path.stem
        tier = path.parent.name.split("_")[-1].upper()
        num = _strategy_number(strategy_id)
        required_data: list[str] = []
        placeholder = False
        text = path.read_text(encoding="utf-8")
        if "placeholder" in text.lower() or "in production" in text.lower():
            placeholder = True

        overview = ""
        scan_logic = ""
        analyze_logic = ""
        key_params: list[dict[str, str]] = []

        try:
            tree = ast.parse(text)
            module_doc = _clean_doc(ast.get_docstring(tree) or "")
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_doc = _clean_doc(ast.get_docstring(node) or "")
                    overview = class_doc or module_doc
                    scan_logic = _extract_method_doc(node, "scan")
                    analyze_logic = _extract_method_doc(node, "analyze")
                    key_params = _extract_key_params(node)
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name) and target.id == "required_data":
                                    try:
                                        parsed = ast.literal_eval(stmt.value)
                                        if isinstance(parsed, list):
                                            required_data = [str(item) for item in parsed]
                                    except Exception:
                                        required_data = []
                    break
        except Exception:
            required_data = []
            overview = ""
            scan_logic = ""
            analyze_logic = ""
            key_params = []

        title_en = strategy_title_en(strategy_id)
        if not overview:
            overview = title_en
        if not scan_logic:
            scan_logic = "No explicit scan docstring found. Refer to source file."
        if not analyze_logic:
            analyze_logic = "No explicit analyze docstring found. Refer to source file."

        details_kr = kr_details.get(num, {})

        if strategy_id == "s06_btc_latency_arb":
            placeholder = True
            required_data = []
            overview = "Deprecated: BTC 5-minute latency strategy removed."
            scan_logic = "Disabled."
            analyze_logic = "Disabled."
            details_kr = {
                "overviewKr": "비활성화: BTC 5분 레이턴시 전략은 제거되었습니다.",
                "scanLogicKr": "비활성화됨.",
                "analyzeLogicKr": "비활성화됨.",
            }

        rows.append(
            {
                "num": num,
                "id": strategy_id,
                "tier": tier,
                "titleEn": title_en,
                "titleKr": KR_NAMES.get(strategy_id, title_en),
                "requiredData": required_data,
                "path": str(path.relative_to(repo_root)),
                "isPlaceholder": placeholder,
                "overview": overview,
                "overviewKr": details_kr.get("overviewKr", ""),
                "scanLogic": scan_logic,
                "scanLogicKr": details_kr.get("scanLogicKr", ""),
                "analyzeLogic": analyze_logic,
                "analyzeLogicKr": details_kr.get("analyzeLogicKr", ""),
                "keyParams": key_params,
            }
        )

    rows.sort(key=lambda row: (row["num"] if row["num"] > 0 else 9999, row["id"]))
    return rows


def run_live_scan(
    runtime: Runtime,
    min_edge: float,
    min_volume: float,
    max_markets: int,
    limit: int,
    strategy_names: Optional[List[str]],
) -> list[dict[str, Any]]:
    markets = runtime.client.get_markets(limit=max_markets, active_only=True)
    filtered_markets = [m for m in markets if m.active and m.volume >= min_volume]
    market_map = {m.condition_id: m for m in filtered_markets}
    bankroll = runtime.client.get_balance()

    if strategy_names:
        strategies = [runtime.strategy_registry.get(name) for name in strategy_names]
        strategies = [s for s in strategies if s is not None]
    else:
        strategies = [runtime.strategy_registry.get(name) for name in CORE_SCANNER_STRATEGIES]
        strategies = [s for s in strategies if s is not None]

    signals: list[dict[str, Any]] = []

    for strategy in strategies:
        assert strategy is not None
        try:
            opportunities = strategy.scan(filtered_markets)
        except Exception:
            logger.debug("scan error for %s", strategy.name, exc_info=True)
            continue

        for opportunity in opportunities:
            try:
                signal = strategy.analyze(opportunity)
            except Exception:
                logger.debug("analyze error for %s", strategy.name, exc_info=True)
                continue

            if signal is None:
                continue

            edge = float(signal.edge)
            if edge < min_edge:
                continue

            market = market_map.get(opportunity.market_id)
            if market is None:
                continue

            yes_price, no_price = yes_no_prices(market)
            suggested_size = None
            try:
                suggested_size = strategy.size_position(signal, bankroll=bankroll)
            except Exception:
                suggested_size = None
            manual_plan = strategy.build_manual_plan(signal, client=runtime.client, size=suggested_size)
            if isinstance(manual_plan, dict):
                manual_plan["size_basis_bankroll_usd"] = round(bankroll, 2)
            market_url = f"https://polymarket.com/event/{market.slug}" if market.slug else None

            signals.append(
                {
                    "marketId": signal.market_id,
                    "question": opportunity.question,
                    "slug": market.slug,
                    "marketUrl": market_url,
                    "category": market.category or opportunity.category or "unknown",
                    "volume": market.volume,
                    "liquidity": market.liquidity,
                    "endDateIso": market.end_date_iso,
                    "strategy": strategy.name,
                    "side": signal.side,
                    "tokenId": signal.token_id,
                    "marketPrice": signal.market_price,
                    "estimatedProb": signal.estimated_prob,
                    "confidence": signal.confidence,
                    "edge": edge,
                    "yesPrice": yes_price,
                    "noPrice": no_price,
                    "manualPlan": manual_plan,
                }
            )

    signals.sort(key=lambda row: (row["edge"], row["confidence"], row["volume"]), reverse=True)
    return signals[:limit]


def build_overview(runtime: Runtime, max_markets: int = 160) -> dict[str, Any]:
    markets = runtime.client.get_markets(limit=max_markets, active_only=True)
    total_volume = sum(m.volume for m in markets)
    avg_liquidity = (sum(m.liquidity for m in markets) / len(markets)) if markets else 0.0

    categories: dict[str, int] = {}
    for market in markets:
        category = (market.category or "unknown").strip().lower() or "unknown"
        categories[category] = categories.get(category, 0) + 1

    category_rows = [{"name": name, "count": count} for name, count in sorted(categories.items(), key=lambda kv: kv[1], reverse=True)]
    top_markets = sorted(markets, key=lambda m: m.volume, reverse=True)[:10]

    volume_curve = [m.volume for m in sorted(top_markets, key=lambda m: m.volume)]
    if len(volume_curve) < 2:
        volume_curve = [0.0, 0.0]

    live_signals = run_live_scan(
        runtime=runtime,
        min_edge=0.02,
        min_volume=1000,
        max_markets=max_markets,
        limit=12,
        strategy_names=None,
    )

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "marketCount": len(markets),
        "totalVolume": total_volume,
        "avgLiquidity": avg_liquidity,
        "signalCount": len(live_signals),
        "categories": category_rows,
        "volumeCurve": volume_curve,
        "topSignals": live_signals,
        "topMarkets": [
            {
                "marketId": m.condition_id,
                "question": m.question,
                "category": m.category or "unknown",
                "volume": m.volume,
                "liquidity": m.liquidity,
                "yesPrice": yes_no_prices(m)[0],
                "noPrice": yes_no_prices(m)[1],
            }
            for m in top_markets
        ],
    }


def build_live_backtest(runtime: Runtime, strategy_name: str, initial_balance: float, slippage_pct: float, max_markets: int) -> dict[str, Any]:
    strategy = runtime.strategy_registry.get(strategy_name)
    if strategy is None:
        raise web.HTTPBadRequest(text=json.dumps({"error": f"Unknown strategy: {strategy_name}"}), content_type="application/json")

    strategy.set_data_registry(runtime.data_registry)

    fetcher = HistoricalFetcher()
    # Pull a wider history window, then prefer the most recent resolved markets.
    samples = fetcher.fetch_closed_binary_markets(max_markets=max_markets * 12, page_size=500)
    samples = list(reversed(samples))

    points: list[HistoricalDataPoint] = []
    for sample in samples:
        history = fetcher.load_or_fetch_history(sample.yes_token)
        if len(history) < 2:
            continue

        entry_ts = sample.close_ts - 24 * 3600
        entry_price = HistoricalFetcher.price_at_or_before(history, entry_ts)
        if entry_price is None:
            entry_ts, entry_price = history[0]

        if entry_price is None or entry_price <= 0 or entry_price >= 1:
            continue

        market = Market(
            condition_id=sample.market_id,
            question=sample.question,
            tokens=[
                {"token_id": f"{sample.market_id}_yes", "outcome": "Yes", "price": str(entry_price)},
                {"token_id": f"{sample.market_id}_no", "outcome": "No", "price": str(1 - entry_price)},
            ],
            end_date_iso=datetime.fromtimestamp(sample.close_ts, tz=timezone.utc).isoformat(),
            # Backtest evaluates pre-resolution snapshots as tradeable states.
            active=True,
            volume=float(sample.volume),
            liquidity=0.0,
            category=sample.category,
            description="",
        )

        points.append(
            HistoricalDataPoint(
                timestamp=datetime.fromtimestamp(int(entry_ts), tz=timezone.utc),
                market=market,
                yes_price=float(entry_price),
                no_price=float(1 - entry_price),
                volume=float(len(history)),
            )
        )

        if len(points) >= max_markets:
            break

    if not points:
        raise web.HTTPBadRequest(text=json.dumps({"error": "No historical points available for backtest"}), content_type="application/json")

    engine = BacktestEngine(strategy=strategy, initial_balance=initial_balance, slippage=slippage_pct / 100.0)
    result = engine.run(points)
    report = BacktestReport(result)

    return {
        "strategyId": strategy_name,
        "initialBalance": result.initial_balance,
        "endingBalance": result.final_balance,
        "annualReturn": report.total_return,
        "sharpe": report.sharpe_ratio,
        "maxDrawdown": report.max_drawdown,
        "winRate": report.win_rate,
        "trades": report.total_trades,
        "equity": result.equity_curve,
        "pointsUsed": len(points),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def json_response(payload: Any, status: int = 200) -> web.Response:
    return web.json_response(payload, status=status)


async def health(_: web.Request) -> web.Response:
    return json_response({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})


async def overview(request: web.Request) -> web.Response:
    runtime: Runtime = request.app["runtime"]
    max_markets = int(request.query.get("max_markets", "160"))
    try:
        payload = build_overview(runtime=runtime, max_markets=max_markets)
        return json_response(payload)
    except Exception as exc:
        logger.error("overview failed: %s", exc)
        return json_response({"error": str(exc), "trace": traceback.format_exc()}, status=500)


async def opportunities(request: web.Request) -> web.Response:
    runtime: Runtime = request.app["runtime"]

    min_edge = float(request.query.get("min_edge", "0.03"))
    min_volume = float(request.query.get("min_volume", "5000"))
    max_markets = int(request.query.get("max_markets", "180"))
    limit = int(request.query.get("limit", "80"))

    raw_strategies = request.query.get("strategies", "")
    strategy_names = [name.strip() for name in raw_strategies.split(",") if name.strip()] or None

    try:
        rows = run_live_scan(
            runtime=runtime,
            min_edge=min_edge,
            min_volume=min_volume,
            max_markets=max_markets,
            limit=limit,
            strategy_names=strategy_names,
        )

        fallback_applied = False
        if not rows and (min_edge > 0.0 or min_volume > 1000):
            rows = run_live_scan(
                runtime=runtime,
                min_edge=0.0,
                min_volume=1000.0,
                max_markets=max_markets,
                limit=limit,
                strategy_names=strategy_names,
            )
            fallback_applied = True

        return json_response({
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "count": len(rows),
            "rows": rows,
            "minEdge": min_edge,
            "minVolume": min_volume,
            "fallbackApplied": fallback_applied,
        })
    except Exception as exc:
        logger.error("opportunities failed: %s", exc)
        return json_response({"error": str(exc), "trace": traceback.format_exc()}, status=500)


async def strategies(request: web.Request) -> web.Response:
    repo_root: Path = request.app["repo_root"]
    try:
        catalog = load_strategy_catalog(repo_root)
        return json_response({"count": len(catalog), "rows": catalog, "generatedAt": datetime.now(timezone.utc).isoformat()})
    except Exception as exc:
        logger.error("strategies failed: %s", exc)
        return json_response({"error": str(exc), "trace": traceback.format_exc()}, status=500)


async def backtest(request: web.Request) -> web.Response:
    runtime: Runtime = request.app["runtime"]

    strategy_name = request.query.get("strategy", "s03_nothing_ever_happens")
    initial_balance = float(request.query.get("initial_balance", "10000"))
    slippage_pct = float(request.query.get("slippage_pct", "0.5"))
    max_markets = int(request.query.get("max_markets", "40"))

    try:
        payload = build_live_backtest(
            runtime=runtime,
            strategy_name=strategy_name,
            initial_balance=initial_balance,
            slippage_pct=slippage_pct,
            max_markets=max_markets,
        )
        return json_response(payload)
    except web.HTTPException:
        raise
    except Exception as exc:
        logger.error("backtest failed: %s", exc)
        return json_response({"error": str(exc), "trace": traceback.format_exc()}, status=500)


def create_app(repo_root: Path) -> web.Application:
    app = web.Application()
    app["repo_root"] = repo_root
    app["runtime"] = Runtime()

    app.router.add_get("/api/health", health)
    app.router.add_get("/api/overview", overview)
    app.router.add_get("/api/opportunities", opportunities)
    app.router.add_get("/api/strategies", strategies)
    app.router.add_get("/api/backtest", backtest)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Live dashboard API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    repo_root = Path(__file__).resolve().parent

    app = create_app(repo_root)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
