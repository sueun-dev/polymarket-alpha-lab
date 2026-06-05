"""Regression tests for the money-path audit fixes.

Covers:
  #1  Kelly returns a USDC dollar stake; orders are denominated in shares,
      so the order layer must convert dollars -> shares (shares = $/price).
  #2  The risk manager must receive the real, accumulating set of open
      positions so max_open_positions and the duplicate-market guard fire.
  #4  A rejected order (truthy object, status="rejected") must not be
      reported as a filled trade.
"""
from datetime import datetime

import pytest

import main
from core.kelly import KellyCriterion, dollars_to_shares
from core.models import Market, Opportunity, Signal, Position
from core.base_strategy import BaseStrategy
from backtest.data_loader import HistoricalDataPoint
from backtest.engine import BacktestEngine


# ---------------------------------------------------------------------------
# Finding #1 -- dollars -> shares at the order boundary
# ---------------------------------------------------------------------------
def test_dollars_to_shares_basic():
    # $1000 at $0.50/share => 2000 shares.
    assert dollars_to_shares(1000.0, 0.50) == pytest.approx(2000.0)


def test_dollars_to_shares_guards_nonpositive_price():
    assert dollars_to_shares(1000.0, 0.0) == 0.0
    assert dollars_to_shares(1000.0, -0.1) == 0.0


def test_order_notional_matches_kelly_stake():
    """The cost of the converted order equals the intended Kelly dollar stake.

    This is the unit that the bug violated: previously the dollar stake was
    passed straight in as a share count, so a $1000 stake became a $500 order
    (price * dollars). After conversion the order notional equals the stake.
    """
    k = KellyCriterion(fraction=0.25, max_fraction=0.25)
    price = 0.50
    stake_usd = k.bet_amount(bankroll=10_000, p=0.70, market_price=price)
    assert stake_usd == pytest.approx(1000.0, abs=1.0)

    shares = dollars_to_shares(stake_usd, price)
    order_notional = price * shares
    assert order_notional == pytest.approx(stake_usd, abs=1e-6)
    # Sanity: shares clearly differ from the raw dollar amount at price != 1.
    assert shares == pytest.approx(2000.0, abs=1.0)


# ---------------------------------------------------------------------------
# Finding #2 -- real, accumulating positions reach the risk check
# ---------------------------------------------------------------------------
class _MultiMarketStrategy(BaseStrategy):
    """Emits one buy signal per distinct market with a large positive edge."""

    name = "multi_market_test"
    tier = "S"
    strategy_id = 0
    required_data: list[str] = []

    def scan(self, markets):
        return [
            Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=0.30,
                metadata={"tokens": m.tokens},
            )
            for m in markets
        ]

    def analyze(self, opp):
        tokens = opp.metadata.get("tokens", [])
        token_id = tokens[0].get("token_id", "") if tokens else "t"
        return Signal(
            market_id=opp.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=0.90,
            market_price=opp.market_price,
            confidence=0.9,
            strategy_name=self.name,
        )

    def execute(self, signal, size, client=None):
        return None


def _dp(cid: str, ts_day: int) -> HistoricalDataPoint:
    market = Market(
        condition_id=cid,
        question=f"Q {cid}?",
        tokens=[{"token_id": f"{cid}_y", "outcome": "Yes", "price": "0.30"}],
        volume=10_000,
    )
    return HistoricalDataPoint(
        timestamp=datetime(2026, 1, ts_day),
        market=market,
        yes_price=0.30,
        no_price=0.70,
        volume=10_000,
    )


def test_backtest_respects_max_open_positions_cap():
    """With the positions fix, the cap actually limits the number of trades.

    Before the fix, current_positions=[] was hardcoded so len() was always 0
    and the cap never fired -- every market traded.
    """
    strategy = _MultiMarketStrategy()
    engine = BacktestEngine(strategy=strategy, initial_balance=1_000_000.0)
    engine.risk.max_open_positions = 3
    engine.risk.min_edge = 0.05

    # 10 distinct markets, all tradeable on edge.
    data = [_dp(f"m{i}", ts_day=i + 1) for i in range(10)]
    result = engine.run(data)

    assert len(result.trades) == 3  # capped, not 10


def test_backtest_blocks_duplicate_market():
    """The duplicate-market guard fires once a position in that market exists."""
    strategy = _MultiMarketStrategy()
    engine = BacktestEngine(strategy=strategy, initial_balance=1_000_000.0)
    engine.risk.max_open_positions = 100  # don't let the cap interfere
    engine.risk.min_edge = 0.05

    # Same market appears on three days; only the first should trade.
    data = [_dp("dup", ts_day=1), _dp("dup", ts_day=2), _dp("dup", ts_day=3)]
    result = engine.run(data)

    assert len(result.trades) == 1


def test_normalize_positions_skips_unparseable():
    norm = main._normalize_positions(
        [
            {"market_id": "0x1", "size": 5, "price": 0.4},
            "garbage",
            {"condition_id": "0x2"},
            42,
        ]
    )
    assert [p.market_id for p in norm] == ["0x1", "0x2"]
    assert all(isinstance(p, Position) for p in norm)


# ---------------------------------------------------------------------------
# Finding #4 -- rejected orders are not counted as fills
# ---------------------------------------------------------------------------
class _RejectingClient:
    """Stands in for a live client whose order is rejected."""

    def place_order(self, token_id, side, price, size, strategy_name=""):
        from core.models import Order

        return Order(
            market_id=token_id,
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            strategy_name=strategy_name,
            status="rejected",
        )


def test_rejected_order_is_truthy_but_not_a_fill():
    """A rejected Order is truthy, so `if order:` was insufficient.

    The fix gates on order.status in {paper, live}. This test documents the
    contract the main loop now relies on.
    """
    client = _RejectingClient()
    order = client.place_order(token_id="t", side="buy", price=0.5, size=10)
    assert order  # truthy object -- the old `if order:` would treat it as success
    assert order.status == "rejected"
    # The condition the main loop now uses:
    assert order.status not in ("paper", "live")


def test_paper_order_counts_as_fill():
    from core.client import PolymarketClient

    c = PolymarketClient(mode="paper")
    order = c.place_order(token_id="t", side="buy", price=0.5, size=10)
    assert order.status == "paper"
    assert order.status in ("paper", "live")


# ---------------------------------------------------------------------------
# Finding #6 -- s04 must not fire the unhedged Polymarket leg
# ---------------------------------------------------------------------------
class _RecordingClient:
    def __init__(self):
        self.orders = []

    def place_order(self, token_id, side, price, size, strategy_name=""):
        from core.models import Order

        self.orders.append((token_id, side, price, size))
        return Order(
            market_id=token_id, token_id=token_id, side=side, price=price,
            size=size, strategy_name=strategy_name, status="paper",
        )


def test_s04_execute_refuses_unhedged_leg():
    from strategies.tier_s.s04_cross_platform_arb import CrossPlatformArb

    s = CrossPlatformArb()
    sig = Signal(
        market_id="0x1", token_id="y1", side="buy", estimated_prob=0.40,
        market_price=0.40, confidence=0.95, strategy_name=s.name,
        metadata={"kalshi_no": 0.30, "arb_profit": 0.29, "requires_kalshi_hedge": True},
    )
    client = _RecordingClient()
    order = s.execute(sig, size=100.0, client=client)
    assert order is None              # half-arb refused
    assert client.orders == []        # no Polymarket order was placed


def test_s04_analyze_does_not_claim_guaranteed_prob():
    """estimated_prob must not be the old 1.0 'guaranteed' value."""
    from strategies.tier_s.s04_cross_platform_arb import CrossPlatformArb
    from core.models import Opportunity

    class _FakeKalshi:
        name = "kalshi"

        def get_markets(self):
            return [{"title": "Fed rate cut", "yes_bid": 70, "ticker": "X"}]

        def match_polymarket_to_kalshi(self, question, markets):
            return markets[0]

    class _Reg:
        def get(self, name):
            return _FakeKalshi() if name == "kalshi" else None

    s = CrossPlatformArb()
    s.set_data_registry(_Reg())
    opp = Opportunity(
        market_id="0x1", question="Fed rate cut?", market_price=0.40,
        metadata={"tokens": [{"token_id": "y1", "outcome": "Yes", "price": "0.40"}]},
    )
    sig = s.analyze(opp)
    assert sig is not None
    assert sig.estimated_prob != 1.0
    assert sig.metadata.get("requires_kalshi_hedge") is True
