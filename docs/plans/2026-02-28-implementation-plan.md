# Polymarket Alpha Lab — Full Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete Python trading bot with 100 strategy modules, backtesting engine, and Streamlit dashboard for Polymarket prediction markets.

**Architecture:** Monorepo single bot with plugin-based strategies. Shared core infrastructure (API client, risk manager, Kelly sizing, market scanner) serves all 100 strategy modules organized by tier. Streamlit dashboard for monitoring.

**Tech Stack:** Python 3.11+, py-clob-client (Polymarket SDK), httpx, pydantic, streamlit, pandas, pytest

---

## Phase 1: Project Scaffold & Core Infrastructure

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.yaml`
- Create: `core/__init__.py`
- Create: `strategies/__init__.py`
- Create: `strategies/tier_s/__init__.py`
- Create: `strategies/tier_a/__init__.py`
- Create: `strategies/tier_b/__init__.py`
- Create: `strategies/tier_c/__init__.py`
- Create: `data/__init__.py`
- Create: `backtest/__init__.py`
- Create: `dashboard/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p core strategies/tier_s strategies/tier_a strategies/tier_b strategies/tier_c data/scrapers backtest dashboard/pages tests
touch core/__init__.py strategies/__init__.py strategies/tier_s/__init__.py strategies/tier_a/__init__.py strategies/tier_b/__init__.py strategies/tier_c/__init__.py data/__init__.py data/scrapers/__init__.py backtest/__init__.py dashboard/__init__.py tests/__init__.py
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "polymarket-alpha-lab"
version = "0.1.0"
description = "Polymarket prediction market trading bot with 100 strategies"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 3: Create requirements.txt**

```
py-clob-client>=0.5.0
httpx>=0.27.0
pydantic>=2.0
pydantic-settings>=2.0
pyyaml>=6.0
python-dotenv>=1.0
pandas>=2.0
numpy>=1.26
streamlit>=1.30
plotly>=5.18
websockets>=12.0
python-telegram-bot>=21.0
aiohttp>=3.9
schedule>=1.2
pytest>=8.0
pytest-asyncio>=0.23
```

**Step 4: Create .env.example**

```env
# Polymarket
POLYMARKET_API_KEY=
POLYMARKET_SECRET=
POLYMARKET_WALLET_ADDRESS=
POLYMARKET_CHAIN_ID=137

# External Data
NOAA_API_TOKEN=
NEWS_API_KEY=
DUNE_API_KEY=

# Cross-Platform
KALSHI_EMAIL=
KALSHI_PASSWORD=

# Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=

# AI
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Infrastructure
POLYGON_RPC_URL=https://polygon-rpc.com
BOT_MODE=paper
```

**Step 5: Create config.yaml**

```yaml
bot:
  mode: paper  # paper | live
  scan_interval: 60
  base_currency: USDC
  log_level: INFO

risk:
  max_position_pct: 0.10
  max_daily_loss_pct: 0.05
  max_open_positions: 20
  kelly_fraction: 0.25  # Quarter-Kelly default
  min_edge: 0.05  # 5% minimum edge to trade

scanner:
  min_volume: 1000
  min_liquidity: 500
  categories: []  # empty = all categories

notifications:
  enabled: false
  telegram: false
  discord: false

strategies:
  # Each strategy can be enabled/disabled with custom params
  # See individual strategy files for param docs
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: project scaffold with directory structure and config"
```

---

### Task 2: Core Models (Pydantic)

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

**Step 1: Write failing tests**

```python
# tests/test_models.py
from core.models import Market, Signal, Opportunity, Order, Position

def test_market_creation():
    m = Market(
        condition_id="0x123",
        question="Will BTC hit 100K?",
        tokens=[{"token_id": "yes_id", "outcome": "Yes"}, {"token_id": "no_id", "outcome": "No"}],
        end_date_iso="2026-12-31T00:00:00Z",
        active=True,
        volume=50000.0,
    )
    assert m.condition_id == "0x123"
    assert m.active is True

def test_signal_edge_calculation():
    s = Signal(
        market_id="0x123",
        token_id="yes_id",
        side="buy",
        estimated_prob=0.70,
        market_price=0.55,
        confidence=0.8,
        strategy_name="test",
    )
    assert s.edge == pytest.approx(0.15, abs=0.001)

def test_opportunity_creation():
    o = Opportunity(
        market_id="0x123",
        question="Test?",
        market_price=0.50,
        category="politics",
    )
    assert o.market_id == "0x123"

def test_order_creation():
    o = Order(
        market_id="0x123",
        token_id="yes_id",
        side="buy",
        price=0.55,
        size=100.0,
        strategy_name="test",
    )
    assert o.total_cost == pytest.approx(55.0, abs=0.01)

def test_position_pnl():
    p = Position(
        market_id="0x123",
        token_id="yes_id",
        side="buy",
        entry_price=0.55,
        size=100.0,
        current_price=0.65,
        strategy_name="test",
    )
    assert p.unrealized_pnl == pytest.approx(10.0, abs=0.01)
```

**Step 2: Run tests — verify they fail**

```bash
pytest tests/test_models.py -v
```

**Step 3: Implement core/models.py**

```python
# core/models.py
from pydantic import BaseModel, computed_field
from datetime import datetime

class Market(BaseModel):
    condition_id: str
    question: str
    tokens: list[dict]
    end_date_iso: str | None = None
    active: bool = True
    volume: float = 0.0
    liquidity: float = 0.0
    category: str = ""
    description: str = ""

class Opportunity(BaseModel):
    market_id: str
    question: str
    market_price: float
    category: str = ""
    metadata: dict = {}

class Signal(BaseModel):
    market_id: str
    token_id: str
    side: str  # "buy" or "sell"
    estimated_prob: float
    market_price: float
    confidence: float
    strategy_name: str
    metadata: dict = {}

    @computed_field
    @property
    def edge(self) -> float:
        return self.estimated_prob - self.market_price

class Order(BaseModel):
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    strategy_name: str
    order_id: str | None = None
    status: str = "pending"
    timestamp: datetime | None = None

    @computed_field
    @property
    def total_cost(self) -> float:
        return self.price * self.size

class Position(BaseModel):
    market_id: str
    token_id: str
    side: str
    entry_price: float
    size: float
    current_price: float
    strategy_name: str

    @computed_field
    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.size
```

**Step 4: Run tests — verify pass**

```bash
pytest tests/test_models.py -v
```

**Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add core data models (Market, Signal, Order, Position)"
```

---

### Task 3: Kelly Criterion Module

**Files:**
- Create: `core/kelly.py`
- Create: `tests/test_kelly.py`

**Step 1: Write failing tests**

```python
# tests/test_kelly.py
import pytest
from core.kelly import KellyCriterion

def test_kelly_basic():
    k = KellyCriterion()
    # 70% prob, 50% market price -> edge = 0.20
    f = k.full_kelly(p=0.70, market_price=0.50)
    assert f == pytest.approx(0.40, abs=0.01)

def test_half_kelly():
    k = KellyCriterion()
    f = k.half_kelly(p=0.70, market_price=0.50)
    assert f == pytest.approx(0.20, abs=0.01)

def test_fractional_kelly():
    k = KellyCriterion(fraction=0.25)
    f = k.optimal_size(p=0.70, market_price=0.50)
    assert f == pytest.approx(0.10, abs=0.01)

def test_no_edge_returns_zero():
    k = KellyCriterion()
    f = k.full_kelly(p=0.50, market_price=0.55)
    assert f == 0.0

def test_kelly_bet_amount():
    k = KellyCriterion(fraction=0.25)
    amount = k.bet_amount(bankroll=10000, p=0.70, market_price=0.50)
    assert amount == pytest.approx(1000.0, abs=1.0)

def test_kelly_max_cap():
    k = KellyCriterion(fraction=0.5, max_fraction=0.06)
    f = k.optimal_size(p=0.95, market_price=0.50)
    assert f <= 0.06
```

**Step 2: Run tests — verify fail**

**Step 3: Implement core/kelly.py**

```python
# core/kelly.py
class KellyCriterion:
    def __init__(self, fraction: float = 0.5, max_fraction: float = 0.06):
        self.fraction = fraction
        self.max_fraction = max_fraction

    def full_kelly(self, p: float, market_price: float) -> float:
        if p <= market_price:
            return 0.0
        # f* = (p - m) / (1 - m)
        f = (p - market_price) / (1 - market_price)
        return max(0.0, f)

    def half_kelly(self, p: float, market_price: float) -> float:
        return self.full_kelly(p, market_price) * 0.5

    def optimal_size(self, p: float, market_price: float) -> float:
        f = self.full_kelly(p, market_price) * self.fraction
        return min(f, self.max_fraction)

    def bet_amount(self, bankroll: float, p: float, market_price: float) -> float:
        f = self.optimal_size(p, market_price)
        return bankroll * f
```

**Step 4: Run tests — verify pass**

**Step 5: Commit**

```bash
git add core/kelly.py tests/test_kelly.py
git commit -m "feat: add Kelly Criterion position sizing module"
```

---

### Task 4: Risk Manager

**Files:**
- Create: `core/risk.py`
- Create: `tests/test_risk.py`

**Step 1: Write failing tests**

```python
# tests/test_risk.py
import pytest
from core.risk import RiskManager
from core.models import Signal, Position

def test_risk_allows_valid_trade():
    rm = RiskManager(max_position_pct=0.10, max_daily_loss_pct=0.05, max_open_positions=20)
    signal = Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.70, market_price=0.55, confidence=0.8, strategy_name="test")
    assert rm.can_trade(signal, bankroll=10000, current_positions=[]) is True

def test_risk_blocks_low_edge():
    rm = RiskManager(min_edge=0.05)
    signal = Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.55, market_price=0.52, confidence=0.8, strategy_name="test")
    assert rm.can_trade(signal, bankroll=10000, current_positions=[]) is False

def test_risk_blocks_max_positions():
    rm = RiskManager(max_open_positions=2)
    positions = [
        Position(market_id=f"0x{i}", token_id=f"t{i}", side="buy", entry_price=0.5, size=100, current_price=0.5, strategy_name="test")
        for i in range(2)
    ]
    signal = Signal(market_id="0x99", token_id="t99", side="buy", estimated_prob=0.70, market_price=0.50, confidence=0.8, strategy_name="test")
    assert rm.can_trade(signal, bankroll=10000, current_positions=positions) is False

def test_daily_loss_tracking():
    rm = RiskManager(max_daily_loss_pct=0.05)
    rm.record_loss(600)
    assert rm.can_trade(
        Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.70, market_price=0.50, confidence=0.8, strategy_name="test"),
        bankroll=10000, current_positions=[]
    ) is False  # 6% > 5% limit

def test_position_size_limit():
    rm = RiskManager(max_position_pct=0.10)
    max_size = rm.max_position_size(bankroll=10000, price=0.50)
    assert max_size == pytest.approx(2000.0, abs=1.0)  # 10% of 10K / 0.50
```

**Step 2: Run tests — verify fail**

**Step 3: Implement core/risk.py**

```python
# core/risk.py
from core.models import Signal, Position

class RiskManager:
    def __init__(
        self,
        max_position_pct: float = 0.10,
        max_daily_loss_pct: float = 0.05,
        max_open_positions: int = 20,
        min_edge: float = 0.05,
    ):
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions
        self.min_edge = min_edge
        self._daily_loss = 0.0

    def can_trade(self, signal: Signal, bankroll: float, current_positions: list[Position]) -> bool:
        if signal.edge < self.min_edge:
            return False
        if len(current_positions) >= self.max_open_positions:
            return False
        if self._daily_loss >= bankroll * self.max_daily_loss_pct:
            return False
        if any(p.market_id == signal.market_id for p in current_positions):
            return False
        return True

    def max_position_size(self, bankroll: float, price: float) -> float:
        max_cost = bankroll * self.max_position_pct
        return max_cost / price if price > 0 else 0.0

    def record_loss(self, amount: float) -> None:
        self._daily_loss += amount

    def reset_daily(self) -> None:
        self._daily_loss = 0.0
```

**Step 4: Run tests — verify pass**

**Step 5: Commit**

```bash
git add core/risk.py tests/test_risk.py
git commit -m "feat: add risk manager with position/loss limits"
```

---

### Task 5: Polymarket API Client

**Files:**
- Create: `core/client.py`
- Create: `tests/test_client.py`

**Step 1: Write failing tests** (mocked — no real API calls)

```python
# tests/test_client.py
import pytest
from unittest.mock import patch, MagicMock
from core.client import PolymarketClient

def test_client_init_paper_mode():
    client = PolymarketClient(mode="paper")
    assert client.mode == "paper"
    assert client.is_live is False

def test_get_markets_returns_list():
    client = PolymarketClient(mode="paper")
    with patch.object(client, '_fetch_markets', return_value=[{"condition_id": "0x1", "question": "Test?", "tokens": [], "active": True}]):
        markets = client.get_markets()
        assert len(markets) >= 1

def test_paper_mode_blocks_real_orders():
    client = PolymarketClient(mode="paper")
    order = client.place_order(token_id="test", side="buy", price=0.50, size=10)
    assert order.status == "paper"

def test_get_orderbook():
    client = PolymarketClient(mode="paper")
    with patch.object(client, '_fetch_orderbook', return_value={"bids": [{"price": "0.49", "size": "100"}], "asks": [{"price": "0.51", "size": "100"}]}):
        book = client.get_orderbook("test_token")
        assert "bids" in book
        assert "asks" in book

def test_get_balance_paper():
    client = PolymarketClient(mode="paper", paper_balance=10000.0)
    assert client.get_balance() == 10000.0
```

**Step 2: Run tests — verify fail**

**Step 3: Implement core/client.py**

```python
# core/client.py
import os
import logging
from datetime import datetime
from core.models import Market, Order

logger = logging.getLogger(__name__)

class PolymarketClient:
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self, mode: str = "paper", paper_balance: float = 10000.0):
        self.mode = mode
        self.is_live = mode == "live"
        self._paper_balance = paper_balance
        self._paper_positions: list[dict] = []
        self._paper_orders: list[Order] = []
        self._clob_client = None

        if self.is_live:
            self._init_live_client()

    def _init_live_client(self):
        try:
            from py_clob_client.client import ClobClient
            api_key = os.environ.get("POLYMARKET_API_KEY", "")
            secret = os.environ.get("POLYMARKET_SECRET", "")
            chain_id = int(os.environ.get("POLYMARKET_CHAIN_ID", "137"))
            self._clob_client = ClobClient(
                self.BASE_URL, key=api_key, chain_id=chain_id,
                creds={"api_key": api_key, "api_secret": secret, "api_passphrase": ""}
            )
        except Exception as e:
            logger.error(f"Failed to init live client: {e}")
            raise

    def get_markets(self, limit: int = 100, active_only: bool = True) -> list[Market]:
        raw = self._fetch_markets(limit=limit, active_only=active_only)
        return [Market(**m) for m in raw]

    def _fetch_markets(self, limit: int = 100, active_only: bool = True) -> list[dict]:
        import httpx
        params = {"limit": limit, "active": active_only}
        resp = httpx.get(f"{self.GAMMA_URL}/markets", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_orderbook(self, token_id: str) -> dict:
        return self._fetch_orderbook(token_id)

    def _fetch_orderbook(self, token_id: str) -> dict:
        import httpx
        resp = httpx.get(f"{self.BASE_URL}/book", params={"token_id": token_id})
        resp.raise_for_status()
        return resp.json()

    def place_order(self, token_id: str, side: str, price: float, size: float, strategy_name: str = "") -> Order:
        order = Order(
            market_id=token_id,
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            strategy_name=strategy_name,
            timestamp=datetime.now(),
        )

        if not self.is_live:
            order.status = "paper"
            order.order_id = f"paper_{len(self._paper_orders)}"
            self._paper_orders.append(order)
            cost = price * size
            if side == "buy":
                self._paper_balance -= cost
            else:
                self._paper_balance += cost
            logger.info(f"[PAPER] Order: {side} {size}x @ {price} | {strategy_name}")
            return order

        if self._clob_client:
            from py_clob_client.order_builder.constants import BUY, SELL
            resp = self._clob_client.create_and_post_order({
                "token_id": token_id,
                "price": price,
                "size": size,
                "side": BUY if side == "buy" else SELL,
            })
            order.order_id = resp.get("orderID", "")
            order.status = "submitted"
        return order

    def get_balance(self) -> float:
        if not self.is_live:
            return self._paper_balance
        if self._clob_client:
            # In live mode, query on-chain USDC balance
            return 0.0  # Implement with web3
        return 0.0

    def get_positions(self) -> list[dict]:
        if not self.is_live:
            return self._paper_positions
        return []
```

**Step 4: Run tests — verify pass**

**Step 5: Commit**

```bash
git add core/client.py tests/test_client.py
git commit -m "feat: add Polymarket API client with paper/live mode"
```

---

### Task 6: Market Scanner

**Files:**
- Create: `core/scanner.py`
- Create: `tests/test_scanner.py`

**Step 1: Write tests**

```python
# tests/test_scanner.py
import pytest
from unittest.mock import MagicMock
from core.scanner import MarketScanner
from core.models import Market

def test_scanner_filters_by_volume():
    client = MagicMock()
    client.get_markets.return_value = [
        Market(condition_id="0x1", question="Q1", tokens=[], volume=5000),
        Market(condition_id="0x2", question="Q2", tokens=[], volume=100),
    ]
    scanner = MarketScanner(client=client, min_volume=1000)
    markets = scanner.scan()
    assert len(markets) == 1
    assert markets[0].condition_id == "0x1"

def test_scanner_filters_inactive():
    client = MagicMock()
    client.get_markets.return_value = [
        Market(condition_id="0x1", question="Q1", tokens=[], active=True, volume=5000),
        Market(condition_id="0x2", question="Q2", tokens=[], active=False, volume=5000),
    ]
    scanner = MarketScanner(client=client, min_volume=0)
    markets = scanner.scan()
    assert len(markets) == 1

def test_scanner_detects_price_spike():
    scanner = MarketScanner(client=MagicMock(), min_volume=0)
    assert scanner.is_price_spike(prev_price=0.50, curr_price=0.70, threshold=0.15) is True
    assert scanner.is_price_spike(prev_price=0.50, curr_price=0.55, threshold=0.15) is False
```

**Step 2-5: Implement, test, commit**

Implementation: Scanner wraps client.get_markets() with filtering logic (volume, liquidity, active status, category). Includes `is_price_spike()` anomaly detector.

```bash
git commit -m "feat: add market scanner with filtering and anomaly detection"
```

---

### Task 7: Base Strategy & Strategy Registry

**Files:**
- Create: `core/base_strategy.py`
- Modify: `strategies/__init__.py` (registry)
- Create: `tests/test_base_strategy.py`

**Step 1: Write tests**

```python
# tests/test_base_strategy.py
import pytest
from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal

class MockStrategy(BaseStrategy):
    name = "mock_strategy"
    tier = "S"
    strategy_id = 0
    required_data = []

    def scan(self, markets):
        return [Opportunity(market_id=m.condition_id, question=m.question, market_price=0.5) for m in markets if m.volume > 1000]

    def analyze(self, opportunity):
        return Signal(market_id=opportunity.market_id, token_id="t1", side="buy", estimated_prob=0.70, market_price=0.50, confidence=0.8, strategy_name=self.name)

    def execute(self, signal, size):
        return None

def test_base_strategy_scan():
    s = MockStrategy()
    markets = [Market(condition_id="0x1", question="Test?", tokens=[], volume=5000)]
    opps = s.scan(markets)
    assert len(opps) == 1

def test_base_strategy_size_position():
    s = MockStrategy()
    signal = Signal(market_id="0x1", token_id="t1", side="buy", estimated_prob=0.70, market_price=0.50, confidence=0.8, strategy_name="test")
    size = s.size_position(signal, bankroll=10000)
    assert size > 0
```

**Step 2-5: Implement, test, commit**

BaseStrategy is an ABC with `scan()`, `analyze()`, `execute()` abstract methods and a default `size_position()` using Kelly.

strategies/__init__.py provides `StrategyRegistry` that auto-discovers all strategy classes from tier_s/, tier_a/, tier_b/, tier_c/ subpackages.

```bash
git commit -m "feat: add base strategy ABC and auto-discovery registry"
```

---

### Task 8: Notifier Module

**Files:**
- Create: `core/notifier.py`
- Create: `tests/test_notifier.py`

Simple Telegram/Discord notification module. Tests mock the actual API calls. Sends: trade executions, opportunity alerts, daily P&L summaries, errors.

```bash
git commit -m "feat: add Telegram/Discord notification module"
```

---

### Task 9: Main CLI Entrypoint

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

Main loop: load config → init client → init risk → register strategies → scan → analyze → execute → notify → sleep → repeat. Includes `--strategy` flag to run specific strategies, `--dry-run` for no-execution mode, `--backtest` for historical replay.

```bash
git commit -m "feat: add main CLI entrypoint with strategy orchestration"
```

---

## Phase 2: Tier S Strategies (#1-#10)

### Task 10: S01 — Reversing Stupidity

**Files:**
- Create: `strategies/tier_s/s01_reversing_stupidity.py`
- Create: `tests/test_s01.py`

**Logic:**
1. `scan()`: Find markets where 24h price change > 15% AND volume spike > 3x average
2. `analyze()`: Calculate base rate for event type, compare to market price. If market price > base_rate + overreaction_threshold → Signal(side="sell"/NO)
3. `execute()`: Place NO order at market price via client
4. Key params: `overreaction_threshold` (default 0.20), `volume_spike_threshold` (default 3.0)

```bash
git commit -m "feat: add S01 Reversing Stupidity strategy"
```

---

### Task 11: S02 — Weather NOAA Arbitrage

**Files:**
- Create: `data/noaa.py`
- Create: `strategies/tier_s/s02_weather_noaa.py`
- Create: `tests/test_s02.py`
- Create: `tests/test_noaa.py`

**data/noaa.py Logic:**
1. Fetch forecast from `api.weather.gov/gridpoints/{office}/{x},{y}/forecast`
2. Parse temperature high/low, precipitation probability
3. Return structured forecast data with confidence intervals

**Strategy Logic:**
1. `scan()`: Find weather markets (filter by "temperature", "weather" keywords)
2. `analyze()`: Compare NOAA forecast probability vs market price for each temperature bracket. If edge > 5% → Signal
3. `execute()`: Place micro-bets ($1-$3) on mispriced temperature brackets
4. Temperature laddering: buy YES on multiple brackets covering forecast range at $0.01-$0.15

```bash
git commit -m "feat: add S02 Weather NOAA arbitrage + NOAA data module"
```

---

### Task 12: S03 — Nothing Ever Happens

**Files:**
- Create: `strategies/tier_s/s03_nothing_ever_happens.py`
- Create: `tests/test_s03.py`

**Logic:**
1. `scan()`: Find "dramatic outcome" markets (keywords: war, crash, collapse, impeach, resign, etc.)
2. `analyze()`: Look up historical base rate for event type. If YES price > base_rate + 20% → Signal(side=NO)
3. `execute()`: Place NO orders. Diversify across categories (politics, geopolitical, economic, crypto)
4. Risk: max 5-10% per market, max 20% single market exposure

```bash
git commit -m "feat: add S03 Nothing Ever Happens strategy"
```

---

### Task 13: S04 — Cross-Platform Arbitrage (Polymarket vs Kalshi)

**Files:**
- Create: `data/kalshi.py`
- Create: `strategies/tier_s/s04_cross_platform_arb.py`
- Create: `tests/test_s04.py`
- Create: `tests/test_kalshi.py`

**data/kalshi.py Logic:**
1. Authenticate with Kalshi API (email/password login)
2. Fetch events and markets with current prices
3. Match Kalshi events to Polymarket events by question similarity

**Strategy Logic:**
1. `scan()`: Fetch prices from both platforms, find matching events
2. `analyze()`: If polymarket_yes + kalshi_no < 1.00 (after fees) → risk-free arb Signal
3. `execute()`: Simultaneously place orders on both platforms
4. **Critical**: Compare settlement rules — different platforms may resolve differently

```bash
git commit -m "feat: add S04 cross-platform arbitrage + Kalshi data module"
```

---

### Task 14: S05 — NegRisk Multi-Outcome Rebalancing

**Files:**
- Create: `strategies/tier_s/s05_negrisk_rebalancing.py`
- Create: `tests/test_s05.py`

**Logic:**
1. `scan()`: Find multi-outcome markets (3+ options). Sum all YES prices
2. `analyze()`: If sum > 1.00 → arb exists. Calculate optimal NO positions on overpriced outcomes
3. `execute()`: Buy NO on overpriced outcomes. Use Convert function (NO → all other YES)
4. Automated monitoring required — opportunities last seconds

```bash
git commit -m "feat: add S05 NegRisk rebalancing arbitrage"
```

---

### Task 15: S06 — BTC/Crypto 15-min Latency Arbitrage

**Files:**
- Create: `data/cex_feed.py` (Binance/Coinbase websocket price feed)
- Create: `strategies/tier_s/s06_btc_latency_arb.py`
- Create: `tests/test_s06.py`

**Logic:**
1. Connect to Binance websocket for real-time BTC price
2. Monitor Polymarket 15-min BTC prediction markets
3. When CEX price crosses decisive threshold → immediately bet on Polymarket
4. Exploit 2-10 second oracle lag

```bash
git commit -m "feat: add S06 BTC latency arbitrage + CEX feed"
```

---

### Task 16: S07 — Settlement Rule Interpretation Arbitrage

**Files:**
- Create: `strategies/tier_s/s07_settlement_rules.py`
- Create: `tests/test_s07.py`

**Logic:**
1. `scan()`: Fetch market descriptions and resolution sources
2. `analyze()`: Parse resolution criteria. Compare headline interpretation vs actual rules. Flag mismatches
3. `execute()`: Bet on side favored by actual resolution rules
4. Cross-platform: compare resolution rules across Polymarket/Kalshi for same event

```bash
git commit -m "feat: add S07 settlement rule interpretation arbitrage"
```

---

### Task 17: S08 — Domain Specialization Framework

**Files:**
- Create: `strategies/tier_s/s08_domain_specialization.py`
- Create: `tests/test_s08.py`

**Logic:**
1. `scan()`: Filter markets by configured domain categories
2. `analyze()`: Independent probability estimation before checking market price. Require minimum confidence threshold. Only trade if edge > 5% AND in specialist domain
3. `execute()`: Half-Kelly sizing, max 2-5% per trade
4. Configurable domains: politics, sports, crypto, weather, AI, geopolitics

```bash
git commit -m "feat: add S08 domain specialization framework"
```

---

### Task 18: S09 — Oracle Latency Exploitation

**Files:**
- Create: `strategies/tier_s/s09_oracle_latency.py`
- Create: `tests/test_s09.py`

**Logic:**
1. Monitor CEX real-time feed AND Polymarket oracle update timing
2. Map oracle update latency per market type
3. When CEX confirms outcome but oracle hasn't updated → bet on confirmed outcome
4. 2-60 second execution window

```bash
git commit -m "feat: add S09 oracle latency exploitation"
```

---

### Task 19: S10 — YES Bias Systematic Exploitation

**Files:**
- Create: `strategies/tier_s/s10_yes_bias.py`
- Create: `tests/test_s10.py`

**Logic:**
1. `scan()`: Scan all markets. Flag where YES appears overpriced (dramatic/exciting outcomes)
2. `analyze()`: Compare base rate to market price. If YES is 1-5% overpriced → NO Signal
3. `execute()`: Small NO positions across hundreds of markets. Statistical edge accumulates over volume
4. Avoid $0.10 or lower YES contracts (longshot traps)

```bash
git commit -m "feat: add S10 YES bias systematic exploitation"
```

---

## Phase 3: Tier A Strategies (#11-#30)

### Task 20-39: Tier A Strategies

Each strategy follows the same pattern:

| Task | Strategy | Key Logic |
|------|----------|-----------|
| 20 | S11 Superforecaster | Bayesian updating, calibration tracking, base rate lookup |
| 21 | S12 High-Prob Harvesting | Scan $0.95+ contracts, buy and hold to settlement |
| 22 | S13 Vitalik Anti-Irrational | Flag "insane" prices, bet NO on extreme scenarios |
| 23 | S14 Cultural/Regional Bias | Filter non-US events, compare local news vs market |
| 24 | S15 News Mean Reversion | Detect 15%+ 24h moves, fade with stop-loss |
| 25 | S16 Primary Source Monitoring | RSS feeds on resolution sources, alert on updates |
| 26 | S17 Whale Basket Copy | Track top wallets via Dune, consensus signal |
| 27 | S18 Automated Market Making | Two-sided quotes, Q-score optimization |
| 28 | S19 Kelly Sizing Framework | (Already implemented in core/kelly.py — this is a wrapper strategy) |
| 29 | S20 Event Catalyst Pre-positioning | Event calendar, position 3-7 days before |
| 30 | S21 Text-Video Delay Sports | Game API feeds, beat video stream by 30-40s |
| 31 | S22 Longshot Bias Exploitation | Sell overpriced $0.05-$0.15 contracts |
| 32 | S23 Correlated Asset Lag | Map related markets, trade lag after primary event |
| 33 | S24 Model vs Market Divergence | Compare 538/Silver Bulletin/Metaculus to market |
| 34 | S25 Liquidity Reward Optimization | Q-score reverse engineering, optimal quote placement |
| 35 | S26 AI Agent Probability Trading | LLM ensemble for probability estimation |
| 36 | S27 Structural Political Mispricing | Electoral structure analysis |
| 37 | S28 Portfolio Betting Agent | Kelly-optimized multi-market portfolio |
| 38 | S29 Earnings Beat Streak | Historical earnings data analysis |
| 39 | S30 Cross-Platform Sportsbook Arb | Polymarket vs DraftKings/Betfair |

Each task: write test → implement strategy class → verify → commit.

```bash
# Example for each:
git commit -m "feat: add S{N} {strategy_name}"
```

---

## Phase 4: Tier B Strategies (#31-#70)

### Task 40-79: Tier B Strategies (40 strategies)

| Range | Strategies |
|-------|-----------|
| 31-35 | Asymmetric low-prob, Parlay optimizer, news speed trading, Polymarket Agents SDK, spread analysis |
| 36-40 | Google Sheets MM, Rust HFT engine wrapper, ML prediction, volume momentum, multi-outcome combinatorial |
| 41-45 | Resolution timing, insider pattern detection, time-weighted momentum, illiquid market exploitation, twitter sentiment reversal |
| 46-50 | Portfolio rebalancing, parallel market monitoring, options-style hedging, stablecoin yield comparison, multi-strategy allocation |
| 51-55 | Weather micro-bet auto, ensemble weather bot, on-chain order flow, papal anti-favorite, mention market NO bias |
| 56-60 | Calendar spread theta, X/Twitter fading, sports text-video, weekend liquidity, hedged airdrop farming |
| 61-65 | Volmex volatility, cross-platform settlement, correlated parlay, Oscar specialization, earnings streak |
| 66-70 | Crypto regulatory, time decay certain, flash crash bot, geopolitical specialization, options synthetic |

Each follows identical pattern: test → implement → verify → commit.

---

## Phase 5: Tier C Strategies (#71-#100)

### Task 80-109: Tier C Strategies (30 strategies)

| Range | Strategies |
|-------|-----------|
| 71-75 | Kaito AI attention, Chainlink oracle timing, Chinese archetype, bot psychology reverse, Reddit contrarian |
| 76-80 | Conditional prob chain, historical analogy, Dune SQL whale, exit timing optimization, news cycle positioning |
| 81-85 | Holiday effect, resolution source speed, multi-language sentiment, token merger arb, micro-cap market monopoly |
| 86-90 | Correlation matrix, ML feature engineering, social graph analysis, gas cost optimization, market creation alpha |
| 91-95 | Automated dispute monitoring, cross-chain arb, prediction tournament signal, volatility surface, market depth analysis |
| 96-100 | Closing line value, smart contract event, multi-timeframe, portfolio insurance, multi-strategy allocation |

---

## Phase 6: Backtesting Engine

### Task 110: Backtest Data Loader

**Files:**
- Create: `backtest/data_loader.py`
- Create: `tests/test_data_loader.py`

Load historical Polymarket market data from CSV/JSON files or Dune Analytics exports. Parse into Market/Price time series.

```bash
git commit -m "feat: add backtest data loader"
```

---

### Task 111: Backtest Engine

**Files:**
- Create: `backtest/engine.py`
- Create: `tests/test_engine.py`

Replay historical data through any strategy's `scan()` → `analyze()` → `execute()` pipeline. Track paper trades with configurable slippage (default 0.5%) and fees.

```bash
git commit -m "feat: add backtest execution engine"
```

---

### Task 112: Backtest Trade Simulator

**Files:**
- Create: `backtest/simulator.py`
- Create: `tests/test_simulator.py`

Simulate order fills with slippage model. Track P&L per trade. Handle partial fills and market impact.

```bash
git commit -m "feat: add backtest trade simulator with slippage"
```

---

### Task 113: Backtest Report Generator

**Files:**
- Create: `backtest/report.py`
- Create: `tests/test_report.py`

Generate performance reports: total return, Sharpe ratio, Sortino ratio, max drawdown, win rate, profit factor, per-strategy attribution. Export to HTML and JSON.

```bash
git commit -m "feat: add backtest performance report generator"
```

---

## Phase 7: Dashboard

### Task 114: Streamlit Dashboard — Overview

**Files:**
- Create: `dashboard/app.py`
- Create: `dashboard/pages/overview.py`

Portfolio overview: total value, active positions, daily P&L chart, strategy allocation pie chart.

```bash
git commit -m "feat: add Streamlit dashboard with overview page"
```

---

### Task 115: Dashboard — Strategy Performance

**Files:**
- Create: `dashboard/pages/strategies.py`

Per-strategy performance table with enable/disable toggles. Win rate, total P&L, Sharpe ratio per strategy.

```bash
git commit -m "feat: add strategy performance dashboard page"
```

---

### Task 116: Dashboard — Live Markets

**Files:**
- Create: `dashboard/pages/markets.py`

Real-time market scanner view. Shows current opportunities detected by active strategies. Sortable by edge, volume, confidence.

```bash
git commit -m "feat: add live markets dashboard page"
```

---

### Task 117: Dashboard — Backtest Viewer

**Files:**
- Create: `dashboard/pages/backtest.py`

Run backtests from UI. Display equity curve, drawdown chart, trade log, and performance metrics.

```bash
git commit -m "feat: add backtest results dashboard page"
```

---

## Phase 8: Polish

### Task 118: Integration Tests

End-to-end test: config load → client init → scanner → strategy scan → signal → risk check → order.

### Task 119: Error Handling & Logging

Structured logging (JSON), graceful error recovery, retry logic for API failures.

### Task 120: Documentation Update

Update README.md with setup instructions, usage guide, strategy descriptions.

### Task 121: Final Commit & Push

```bash
git add -A
git commit -m "feat: complete Polymarket Alpha Lab v0.1.0 — 100 strategies, backtest, dashboard"
git push origin main
```
