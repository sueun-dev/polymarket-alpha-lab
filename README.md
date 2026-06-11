# Polymarket Alpha Lab

Polymarket Alpha Lab is a strategy research repository for prediction markets.
It contains research notes, 100 strategy modules, read-only market-data tools,
backtesting utilities, and dashboards for studying strategy signals.

This repository is not a live trading bot. It does not contain wallet
credential handling, paper/live order placement, Telegram trade alerts, or an
infinite automated execution loop.

## What This Project Does

- Catalogs 100 Polymarket strategy ideas across S/A/B/C tiers.
- Implements each strategy as Python logic that scans markets and emits
  analytical `Signal` objects.
- Pulls read-only market data from public Polymarket endpoints.
- Provides optional external data providers for NOAA weather, Kalshi, news,
  base rates, historical prices, and derived market features.
- Supports historical backtests for strategy evaluation.
- Provides Streamlit and React dashboards for strategy exploration.
- Includes English and Korean research documents under `research/`.

## What Was Removed

The repository intentionally does not include the old trading-bot execution
surface:

- no `place_order(...)` client method
- no paper/live mode
- no wallet or Polymarket private-key configuration
- no risk manager for live position gates
- no notifier module for trade alerts
- no `run` command that loops forever and executes orders
- no strategy `execute(...)` methods

Strategies now stop at signal generation. Any real execution layer should live
outside this repository and be reviewed separately.

## Research Documents

| File | Language | Description |
| --- | --- | --- |
| `research/EN-polymarket-market-inefficiencies.md` | EN | Market inefficiency research, examples, academic context, risks, and sources. |
| `research/EN-polymarket-top-100-strategies.md` | EN | Top 100 strategy catalog ranked by S/A/B/C tier. |
| `research/KR-polymarket-top-100-strategies.md` | KR | Korean version of the Top 100 strategy catalog. |
| `research/KR-단일전략-TOP10.md` | KR | Korean Top 10 single-strategy research note. |
| `research/KR-조합전략-TOP10.md` | KR | Korean Top 10 combination-strategy research note. |

## Strategy Tiers

| Tier | Range | Meaning |
| --- | --- | --- |
| S | #1-10 | Highest-priority ideas with stronger documented evidence. |
| A | #11-30 | Strong strategies backed by data or research. |
| B | #31-70 | Plausible strategies with reasonable evidence. |
| C | #71-100 | Experimental strategies that need more validation. |

## Quick Start

```bash
git clone https://github.com/sueun-dev/polymarket-alpha-lab.git
cd polymarket-alpha-lab

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python3 main.py list
```

## CLI Commands

List all strategies:

```bash
python3 main.py list
```

Run a one-shot read-only strategy scan:

```bash
python3 main.py scan --limit 20
python3 main.py scan --strategy s02_weather_noaa
```

Run backtests using historical data files:

```bash
python3 main.py backtest --data-dir data/historical/
python3 main.py backtest --strategy s01_reversing_stupidity
```

Collect historical Polymarket data for research:

```bash
python3 main.py collect-data
```

Run the Streamlit dashboard:

```bash
streamlit run dashboard/app.py
```

Run the React dashboard with the live read-only API:

```bash
python3 dashboard_api.py --host 127.0.0.1 --port 8001

cd dashboard-react
npm init -y
npm install react react-dom vite @vitejs/plugin-react
npx vite
```

The React app opens on `http://localhost:3001` and proxies `/api` to the
backend on port `8001`.

## Project Structure

```text
core/
  base_strategy.py        # Strategy interface: scan/analyze only
  kelly.py                # Research/backtest sizing helper
  models.py               # Market, Opportunity, Signal, Position models
  native_weather_kernel.py
  scanner.py              # Read-only market filtering
data/
  polymarket.py           # Read-only Polymarket public data client
  historical_fetcher.py   # Historical market and price-history retrieval
  noaa.py                 # NOAA weather provider
  kalshi_client.py        # Kalshi read-only data provider
  news_client.py          # Optional GNews provider
  base_rates.py           # Category base-rate priors
  feature_engine.py       # Momentum/volatility features
strategies/
  tier_s/                 # Strategies #1-10
  tier_a/                 # Strategies #11-30
  tier_b/                 # Strategies #31-70
  tier_c/                 # Strategies #71-100
backtest/                 # Historical strategy evaluation
dashboard/                # Streamlit dashboard
dashboard-react/          # React dashboard UI
research/                 # Strategy research documents
native/                   # Optional native weather probability kernel source
tools/                    # Standalone research tools
tests/                    # Pytest suite
main.py                   # Strategy research CLI
dashboard_api.py          # Read-only API for the React dashboard
config.yaml               # Scanner/backtest/data settings
.env.example              # Optional data-provider keys only
```

## Configuration

`config.yaml` only controls analysis settings:

- `scanner.max_markets`
- `scanner.min_volume`
- `scanner.min_liquidity`
- `scanner.categories`
- `signals.min_edge`
- `backtest.initial_balance`
- `backtest.slippage`
- `data.max_markets`

`.env.example` only includes optional data-provider keys. It does not include
wallet keys or Polymarket private credentials.

## Tests

```bash
python3 -m pytest tests/ -q
```

## Disclaimer

This repository is for research and education. Prediction market strategies can
lose money, and this repository does not provide investment advice or a
production execution system.
