# Polymarket Alpha Lab — Trading Bot System Design

**Date:** 2026-02-28
**Status:** Approved
**Language:** Python 3.11+
**Architecture:** Monorepo single bot with 100 strategy plugins

---

## 1. Overview

Build a fully executable Python trading bot that implements all 100 strategies from the curated strategy document. Each strategy is a self-contained plugin module that plugs into shared core infrastructure. Users configure `.env` and `config.yaml`, then run any combination of strategies via CLI.

## 2. Directory Structure

```
polymarket-alpha-lab/
├── core/                        # Shared infrastructure
│   ├── __init__.py
│   ├── client.py                # Polymarket CLOB API wrapper (py-clob-client)
│   ├── risk.py                  # Portfolio risk management
│   ├── kelly.py                 # Kelly Criterion / Half-Kelly position sizing
│   ├── scanner.py               # Market scanner — scans all active markets
│   ├── notifier.py              # Telegram / Discord notifications
│   └── base_strategy.py         # Abstract base class for all strategies
├── strategies/                  # 100 strategy modules
│   ├── __init__.py              # Strategy registry (auto-discovers all strategies)
│   ├── tier_s/                  # #1-#10: Verified alpha
│   │   ├── __init__.py
│   │   ├── s01_reversing_stupidity.py
│   │   ├── s02_weather_noaa.py
│   │   ├── s03_nothing_ever_happens.py
│   │   ├── s04_cross_platform_arb.py
│   │   ├── s05_negrisk_rebalancing.py
│   │   ├── s06_news_speed_trading.py
│   │   ├── s07_high_prob_harvesting.py
│   │   ├── s08_whale_copy_trading.py
│   │   ├── s09_mean_reversion.py
│   │   └── s10_q_score_decay.py
│   ├── tier_a/                  # #11-#30: Strong edge (20 strategies)
│   │   └── ...
│   ├── tier_b/                  # #31-#70: Solid strategies (40 strategies)
│   │   └── ...
│   └── tier_c/                  # #71-#100: Experimental edge (30 strategies)
│       └── ...
├── data/                        # External data collectors
│   ├── __init__.py
│   ├── noaa.py                  # NOAA weather API
│   ├── kalshi.py                # Kalshi price fetcher
│   ├── sentiment.py             # Twitter/Reddit sentiment (snscrape, PRAW)
│   ├── onchain.py               # Polygon on-chain data (Dune Analytics)
│   ├── news.py                  # News API / RSS feeds
│   └── scrapers/                # Custom scrapers
│       ├── polymarket_scraper.py
│       └── odds_scraper.py
├── backtest/                    # Backtesting engine
│   ├── __init__.py
│   ├── engine.py                # Backtest execution engine
│   ├── data_loader.py           # Historical market data loader
│   ├── simulator.py             # Trade simulator with slippage/fees
│   └── report.py                # Performance report (Sharpe, MDD, PnL)
├── dashboard/                   # Web dashboard
│   ├── __init__.py
│   ├── app.py                   # Streamlit dashboard
│   └── pages/
│       ├── overview.py          # Portfolio overview
│       ├── strategies.py        # Per-strategy performance
│       ├── markets.py           # Live market scanner view
│       └── backtest.py          # Backtest results viewer
├── tests/                       # Unit & integration tests
│   └── ...
├── .env.example                 # Environment variable template
├── config.yaml                  # Strategy config (enable/disable, params)
├── main.py                      # CLI entrypoint
├── requirements.txt
└── pyproject.toml
```

## 3. Core Modules

### 3.1 client.py — Polymarket API Client

Wraps `py-clob-client` SDK. Provides:
- `get_markets()` — fetch all active markets
- `get_market(id)` — fetch single market details
- `get_orderbook(token_id)` — get current orderbook
- `place_order(token_id, side, price, size)` — place limit order
- `cancel_order(order_id)` — cancel open order
- `get_positions()` — current portfolio positions
- `get_balance()` — USDC balance
- Rate limiting and retry logic built-in

### 3.2 risk.py — Risk Manager

- `max_position_pct`: Max % of portfolio in single market (default 10%)
- `max_daily_loss`: Daily stop-loss threshold
- `max_open_positions`: Maximum concurrent positions
- `correlation_check()`: Prevent correlated positions exceeding limit
- `can_trade(signal) -> bool`: Gate check before any order

### 3.3 kelly.py — Position Sizing

- `kelly_fraction(p, b)` → optimal bet fraction
- `half_kelly(p, b)` → conservative sizing (default)
- `fractional_kelly(p, b, fraction)` → configurable
- Input: estimated probability `p`, payout odds `b`
- Output: fraction of bankroll to bet

### 3.4 scanner.py — Market Scanner

- Polls Polymarket API on interval (configurable, default 60s)
- Filters markets by: volume, liquidity, time to resolution, category
- Detects anomalies: sudden price moves, volume spikes, new markets
- Feeds filtered markets to active strategies

### 3.5 base_strategy.py — Strategy Interface

```python
class BaseStrategy(ABC):
    name: str
    tier: str  # S, A, B, C
    strategy_id: int  # 1-100
    required_data: list[str]  # ["noaa", "kalshi", etc.]

    @abstractmethod
    def scan(self, markets: list[Market]) -> list[Opportunity]: ...

    @abstractmethod
    def analyze(self, opportunity: Opportunity) -> Signal | None: ...

    def size_position(self, signal: Signal) -> float:
        return self.kelly.half_kelly(signal.probability, signal.odds)

    @abstractmethod
    def execute(self, signal: Signal, size: float) -> Order | None: ...

    def on_resolution(self, market: Market, outcome: str) -> None: ...
```

### 3.6 notifier.py

- Telegram bot integration (python-telegram-bot)
- Discord webhook support
- Events: trade executed, opportunity detected, daily P&L summary, errors

## 4. Data Modules

| Module | API/Source | Rate Limit | Strategies |
|--------|-----------|------------|------------|
| noaa.py | api.weather.gov | 5 req/s | #2, #51, #52 |
| kalshi.py | Kalshi REST API | 10 req/s | #4, #62 |
| sentiment.py | Twitter API / PRAW | varies | #1, #57, #75 |
| onchain.py | Dune Analytics API | 40 req/min | #53, #22 |
| news.py | NewsAPI / RSS | 100 req/day | #6, #14, #69 |

## 5. Backtest Engine

- `data_loader.py`: Load historical Polymarket data (CSV/API/Dune exports)
- `engine.py`: Replay historical data through strategy logic
- `simulator.py`: Simulate fills with configurable slippage (default 0.5%) and fees
- `report.py`: Generate performance metrics:
  - Total return, Sharpe ratio, Sortino ratio
  - Max drawdown, win rate, profit factor
  - Per-strategy attribution
  - Export to HTML/JSON

## 6. Dashboard (Streamlit)

- **Overview page**: Total portfolio value, active positions, daily P&L chart
- **Strategies page**: Per-strategy performance table, enable/disable toggle
- **Markets page**: Live scanner results, opportunity alerts
- **Backtest page**: Run backtests from UI, view results

## 7. Configuration

### .env.example
```
POLYMARKET_API_KEY=
POLYMARKET_SECRET=
POLYMARKET_WALLET_ADDRESS=
POLYGON_RPC_URL=
KALSHI_EMAIL=
KALSHI_PASSWORD=
NOAA_API_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
NEWS_API_KEY=
DUNE_API_KEY=
```

### config.yaml
```yaml
bot:
  mode: paper  # paper | live
  scan_interval: 60  # seconds
  base_currency: USDC

risk:
  max_position_pct: 0.10
  max_daily_loss: 0.05
  max_open_positions: 20
  kelly_fraction: 0.5  # Half-Kelly default

strategies:
  s01_reversing_stupidity:
    enabled: true
    params:
      overreaction_threshold: 0.20
      max_bet_per_market: 500
  s02_weather_noaa:
    enabled: true
    params:
      cities: ["new_york", "london", "seoul"]
      min_edge: 0.05
      max_bet: 3
  # ... all 100 strategies configurable
```

## 8. Execution Flow

```
main.py → load config → init client → init risk manager
       → register enabled strategies
       → scanner.poll_markets()
       → for each strategy:
           opportunities = strategy.scan(markets)
           for opp in opportunities:
               signal = strategy.analyze(opp)
               if signal and risk.can_trade(signal):
                   size = strategy.size_position(signal)
                   order = strategy.execute(signal, size)
                   notifier.send(order)
       → sleep(scan_interval) → repeat
```

## 9. Implementation Priority

Phase 1 (Core): client.py, risk.py, kelly.py, base_strategy.py, scanner.py
Phase 2 (Tier S): 10 strategies (#1-#10) + NOAA/Kalshi data modules
Phase 3 (Tier A): 20 strategies (#11-#30) + sentiment/onchain/news data
Phase 4 (Tier B): 40 strategies (#31-#70)
Phase 5 (Tier C): 30 strategies (#71-#100)
Phase 6 (Backtest): engine, data_loader, simulator, report
Phase 7 (Dashboard): Streamlit app with all pages
Phase 8 (Polish): tests, documentation, error handling
