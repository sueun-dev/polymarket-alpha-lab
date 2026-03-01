"""Tests for data.backtest_data_builder -- BacktestDataBuilder and trade_profit."""
from __future__ import annotations

import csv
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import pytest

from backtest.data_loader import HistoricalDataPoint
from core.models import Market
from data.backtest_data_builder import (
    BUY_FEE,
    BacktestDataBuilder,
    trade_profit,
)
from data.historical_fetcher import MarketSample


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sample(
    *,
    market_id: str = "m1",
    question: str = "Will it rain?",
    category: str = "weather",
    close_ts: int = 100_000,
    yes_token: str = "tok_yes",
    yes_won: bool = True,
) -> MarketSample:
    return MarketSample(
        market_id=market_id,
        question=question,
        category=category,
        close_ts=close_ts,
        yes_token=yes_token,
        yes_won=yes_won,
    )


def _make_history(
    close_ts: int = 100_000,
    price: float = 0.75,
    span_minutes: int = 180,
    step: int = 60,
) -> List[Tuple[int, float]]:
    """Create a simple price history covering [close_ts - span*60, close_ts]."""
    start = close_ts - span_minutes * 60
    return [(t, price) for t in range(start, close_ts + 1, step)]


def _make_data_point(
    ts_epoch: int = 50_000,
    condition_id: str = "m1",
    question: str = "Test?",
    yes_price: float = 0.60,
) -> HistoricalDataPoint:
    no_price = 1.0 - yes_price
    market = Market(
        condition_id=condition_id,
        question=question,
        tokens=[
            {"token_id": f"{condition_id}_yes", "outcome": "Yes", "price": str(yes_price)},
            {"token_id": f"{condition_id}_no", "outcome": "No", "price": str(no_price)},
        ],
        volume=0.0,
    )
    return HistoricalDataPoint(
        timestamp=datetime.fromtimestamp(ts_epoch, tz=timezone.utc),
        market=market,
        yes_price=yes_price,
        no_price=no_price,
        volume=0.0,
    )


# ---------------------------------------------------------------------------
# BacktestDataBuilder.__init__
# ---------------------------------------------------------------------------


class TestBacktestDataBuilderInit:
    def test_default_fetcher(self):
        builder = BacktestDataBuilder()
        assert builder.fetcher is not None

    def test_custom_fetcher(self):
        from data.historical_fetcher import HistoricalFetcher

        fetcher = HistoricalFetcher(cache_dir=Path("/tmp/custom"))
        builder = BacktestDataBuilder(fetcher=fetcher)
        assert builder.fetcher is fetcher


# ---------------------------------------------------------------------------
# samples_to_data_points
# ---------------------------------------------------------------------------


class TestSamplesToDataPoints:
    """Test conversion of MarketSamples + histories into HistoricalDataPoints."""

    def test_normal_case(self):
        """Samples with matching histories produce data points at each horizon."""
        sample = _make_sample(close_ts=100_000)
        history = _make_history(close_ts=100_000, price=0.75, span_minutes=180, step=60)
        histories = {sample.yes_token: history}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)

        # 5 horizons: 5, 15, 30, 60, 120 minutes
        assert len(points) == 5

    def test_empty_samples(self):
        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([], {})
        assert points == []

    def test_missing_history_skipped(self):
        """A sample with no matching history key produces no data points."""
        sample = _make_sample(yes_token="tok_missing")
        histories = {"tok_other": [(1000, 0.5)]}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)
        assert points == []

    def test_empty_history_skipped(self):
        """A sample whose history is an empty list produces no data points."""
        sample = _make_sample()
        histories = {sample.yes_token: []}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)
        assert points == []

    def test_timestamps_are_correct(self):
        """Each data point timestamp should be close_ts - horizon*60."""
        close_ts = 100_000
        sample = _make_sample(close_ts=close_ts)
        history = _make_history(close_ts=close_ts, price=0.80, span_minutes=180, step=60)
        histories = {sample.yes_token: history}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)

        expected_ts = sorted(
            [close_ts - h * 60 for h in (5, 15, 30, 60, 120)]
        )
        actual_ts = sorted(
            [int(dp.timestamp.replace(tzinfo=timezone.utc).timestamp()) for dp in points]
        )
        assert actual_ts == expected_ts

    def test_yes_no_prices_sum_to_one(self):
        """yes_price + no_price should always equal 1.0."""
        sample = _make_sample(close_ts=100_000)
        history = _make_history(close_ts=100_000, price=0.65, span_minutes=180, step=60)
        histories = {sample.yes_token: history}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)

        for dp in points:
            assert dp.yes_price + dp.no_price == pytest.approx(1.0)

    def test_data_points_sorted_by_timestamp(self):
        """Output should be sorted chronologically."""
        # Two samples with different close times
        s1 = _make_sample(market_id="m1", close_ts=200_000, yes_token="tok1")
        s2 = _make_sample(market_id="m2", close_ts=100_000, yes_token="tok2")
        h1 = _make_history(close_ts=200_000, price=0.5, span_minutes=180, step=60)
        h2 = _make_history(close_ts=100_000, price=0.6, span_minutes=180, step=60)
        histories = {"tok1": h1, "tok2": h2}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([s1, s2], histories)

        timestamps = [dp.timestamp for dp in points]
        assert timestamps == sorted(timestamps)

    def test_market_model_fields(self):
        """Market model should have correct condition_id, question, tokens, category."""
        sample = _make_sample(
            market_id="m_special",
            question="Will BTC hit $100k?",
            category="crypto",
            close_ts=100_000,
        )
        history = _make_history(close_ts=100_000, price=0.90, span_minutes=180, step=60)
        histories = {sample.yes_token: history}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)

        assert len(points) > 0
        dp = points[0]
        assert dp.market.condition_id == "m_special"
        assert dp.market.question == "Will BTC hit $100k?"
        assert dp.market.category == "crypto"
        assert len(dp.market.tokens) == 2
        assert dp.market.tokens[0]["outcome"] == "Yes"
        assert dp.market.tokens[1]["outcome"] == "No"
        assert dp.market.tokens[0]["token_id"] == "m_special_yes"
        assert dp.market.tokens[1]["token_id"] == "m_special_no"

    def test_horizon_with_no_price_at_ts_skipped(self):
        """If price_at_or_before returns None for a horizon, that horizon is skipped."""
        close_ts = 100_000
        sample = _make_sample(close_ts=close_ts)
        # History only covers 50 minutes before close -> 60min and 120min horizons will fail
        history = _make_history(
            close_ts=close_ts, price=0.70, span_minutes=50, step=60
        )
        histories = {sample.yes_token: history}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)

        # Only 5, 15, 30 minute horizons should succeed (all within 50min)
        actual_offsets = sorted(
            [close_ts - int(dp.timestamp.timestamp()) for dp in points]
        )
        # 5*60=300, 15*60=900, 30*60=1800 should be present; 60*60=3600 and 120*60=7200 absent
        for offset in actual_offsets:
            assert offset in (300, 900, 1800)

    def test_multiple_samples(self):
        """Multiple samples all generate data points."""
        samples = [
            _make_sample(market_id="m1", close_ts=100_000, yes_token="tok1"),
            _make_sample(market_id="m2", close_ts=100_000, yes_token="tok2"),
        ]
        histories = {
            "tok1": _make_history(close_ts=100_000, price=0.5, span_minutes=180, step=60),
            "tok2": _make_history(close_ts=100_000, price=0.6, span_minutes=180, step=60),
        }

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points(samples, histories)

        # Each sample should contribute 5 data points (one per horizon)
        assert len(points) == 10

    def test_volume_is_zero(self):
        """Volume should default to 0.0 for all generated data points."""
        sample = _make_sample(close_ts=100_000)
        history = _make_history(close_ts=100_000, price=0.5, span_minutes=180, step=60)
        histories = {sample.yes_token: history}

        builder = BacktestDataBuilder()
        points = builder.samples_to_data_points([sample], histories)

        for dp in points:
            assert dp.volume == 0.0


# ---------------------------------------------------------------------------
# export_csv
# ---------------------------------------------------------------------------


class TestExportCSV:
    """Test CSV export of HistoricalDataPoints."""

    def test_write_and_read_back(self):
        """Write data points to CSV, read back and verify content."""
        dp1 = _make_data_point(ts_epoch=50_000, condition_id="m1", yes_price=0.60)
        dp2 = _make_data_point(ts_epoch=60_000, condition_id="m2", yes_price=0.40)

        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.csv")
            count = builder.export_csv([dp1, dp2], path)

            assert count == 2

            with open(path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["condition_id"] == "m1"
            assert float(rows[0]["yes_price"]) == pytest.approx(0.60, abs=1e-5)
            assert float(rows[0]["no_price"]) == pytest.approx(0.40, abs=1e-5)
            assert rows[1]["condition_id"] == "m2"
            assert float(rows[1]["yes_price"]) == pytest.approx(0.40, abs=1e-5)
            assert float(rows[1]["no_price"]) == pytest.approx(0.60, abs=1e-5)

    def test_csv_headers(self):
        """CSV should have the correct header row."""
        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "headers.csv")
            builder.export_csv([], path)

            with open(path) as f:
                reader = csv.reader(f)
                header = next(reader)

            assert header == [
                "timestamp",
                "condition_id",
                "question",
                "yes_price",
                "no_price",
                "volume",
            ]

    def test_row_count_matches_input(self):
        """Number of written rows should match the number of data points."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(7)]

        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "count.csv")
            count = builder.export_csv(points, path)

            assert count == 7

            with open(path) as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                data_rows = list(reader)

            assert len(data_rows) == 7

    def test_creates_parent_directories(self):
        """Nested parent directories should be created automatically."""
        dp = _make_data_point()
        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = str(Path(tmpdir) / "a" / "b" / "c" / "data.csv")
            count = builder.export_csv([dp], nested_path)

            assert count == 1
            assert Path(nested_path).exists()

    def test_empty_data_points_writes_header_only(self):
        """Empty input should produce a CSV with just the header row."""
        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "empty.csv")
            count = builder.export_csv([], path)

            assert count == 0

            with open(path) as f:
                content = f.read()

            lines = content.strip().split("\n")
            assert len(lines) == 1  # only header

    def test_csv_round_trip_with_data_loader(self):
        """CSV produced by export_csv should be loadable by DataLoader."""
        from backtest.data_loader import DataLoader

        dp = _make_data_point(
            ts_epoch=50_000, condition_id="m_rt", question="Round trip?", yes_price=0.55
        )
        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "round_trip.csv")
            builder.export_csv([dp], path)

            loader = DataLoader()
            loaded = loader.load_csv(path)

            assert len(loaded) == 1
            assert loaded[0].market.condition_id == "m_rt"
            assert loaded[0].yes_price == pytest.approx(0.55, abs=1e-5)
            assert loaded[0].no_price == pytest.approx(0.45, abs=1e-5)

    def test_timestamp_format_is_isoformat(self):
        """Timestamps in CSV should be ISO 8601 format."""
        dp = _make_data_point(ts_epoch=1_700_000_000)
        builder = BacktestDataBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "ts.csv")
            builder.export_csv([dp], path)

            with open(path) as f:
                reader = csv.DictReader(f)
                row = next(reader)

            # Should parse without error
            parsed = datetime.fromisoformat(row["timestamp"])
            assert parsed is not None


# ---------------------------------------------------------------------------
# split_train_test
# ---------------------------------------------------------------------------


class TestSplitTrainTest:
    """Test chronological train/test splitting."""

    def test_normal_70_30_split(self):
        """Default 70/30 split of 10 items -> 7 train, 3 test."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(10)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points)

        assert len(train) == 7
        assert len(test) == 3

    def test_empty_data(self):
        builder = BacktestDataBuilder()
        train, test = builder.split_train_test([])

        assert train == []
        assert test == []

    def test_single_item(self):
        """Single item: idx=max(1, min(0, 0)) -> 1, but clamped to len-1=0, so idx=max(1,0)=1... but len-1=0, idx=min(1,0)=0, idx=max(1,0)=1 -> error. Let's check the actual logic."""
        # With 1 item, train_ratio=0.7: idx=int(0.7)=0, max(1, min(0, 0))=max(1,0)=1.
        # But len=1, so idx=min(1, 0)=0 FIRST, then max(1, 0)=1.
        # Wait: idx = max(1, min(idx, len-1)) = max(1, min(0, 0)) = max(1, 0) = 1.
        # But data_points[:1] = [item], data_points[1:] = []. This is fine.
        points = [_make_data_point(ts_epoch=1000)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points)

        # With single item, idx=max(1, min(0, 0))=1 but len-1=0 so min(0,0)=0 then max(1,0)=1
        # train = points[:1] = [item], test = points[1:] = []
        # Actually: idx = int(1 * 0.7) = 0, then max(1, min(0, 0)) = 1
        # So we get 1 train, 0 test... but the code says min(idx, len-1) first.
        # idx = int(0.7) = 0, min(0, 0) = 0, max(1, 0) = 1
        # train = [:1], test = [1:] = []
        assert len(train) + len(test) == 1

    def test_two_items(self):
        """Two items: idx = int(2*0.7)=1, min(1,1)=1, max(1,1)=1. Split: [:1], [1:]."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(2)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points)

        assert len(train) == 1
        assert len(test) == 1

    def test_custom_ratio(self):
        """50/50 split of 10 items -> 5 train, 5 test."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(10)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points, train_ratio=0.5)

        assert len(train) == 5
        assert len(test) == 5

    def test_high_ratio(self):
        """90/10 split of 10 items -> 9 train, 1 test."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(10)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points, train_ratio=0.9)

        assert len(train) == 9
        assert len(test) == 1

    def test_low_ratio(self):
        """10/90 split of 10 items -> at least 1 train (clamped)."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(10)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points, train_ratio=0.1)

        assert len(train) >= 1
        assert len(test) >= 1
        assert len(train) + len(test) == 10

    def test_chronological_order_preserved(self):
        """Train and test sets maintain original chronological order."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(10)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points)

        train_ts = [dp.timestamp for dp in train]
        test_ts = [dp.timestamp for dp in test]

        assert train_ts == sorted(train_ts)
        assert test_ts == sorted(test_ts)

        # All train timestamps should be before all test timestamps
        if train and test:
            assert train[-1].timestamp <= test[0].timestamp

    def test_no_overlap_between_train_and_test(self):
        """Train and test sets together should equal the original list."""
        points = [_make_data_point(ts_epoch=i * 1000) for i in range(10)]

        builder = BacktestDataBuilder()
        train, test = builder.split_train_test(points)

        combined = train + test
        assert len(combined) == len(points)
        for i, dp in enumerate(combined):
            assert dp.timestamp == points[i].timestamp


# ---------------------------------------------------------------------------
# trade_profit
# ---------------------------------------------------------------------------


class TestTradeProfit:
    """Test trade profit/loss calculation."""

    def test_yes_bet_yes_wins(self):
        """YES bet where YES wins -> profit."""
        won, profit = trade_profit("YES", 0.60, yes_won=True)
        assert won is True
        # cost = 0.60 * 1.01 = 0.606, payout = 1.0, profit = 0.394
        assert profit == pytest.approx(1.0 - 0.60 * 1.01, abs=1e-9)
        assert profit > 0

    def test_yes_bet_no_wins(self):
        """YES bet where NO wins -> loss."""
        won, profit = trade_profit("YES", 0.60, yes_won=False)
        assert won is False
        # cost = 0.60 * 1.01 = 0.606, payout = 0.0, profit = -0.606
        assert profit == pytest.approx(0.0 - 0.60 * 1.01, abs=1e-9)
        assert profit < 0

    def test_no_bet_yes_wins(self):
        """NO bet where YES wins -> loss."""
        won, profit = trade_profit("NO", 0.60, yes_won=True)
        assert won is False
        # cost = 0.40 * 1.01 = 0.404, payout = 0.0, profit = -0.404
        assert profit == pytest.approx(0.0 - 0.40 * 1.01, abs=1e-9)
        assert profit < 0

    def test_no_bet_no_wins(self):
        """NO bet where NO wins -> profit."""
        won, profit = trade_profit("NO", 0.60, yes_won=False)
        assert won is True
        # cost = 0.40 * 1.01 = 0.404, payout = 1.0, profit = 0.596
        assert profit == pytest.approx(1.0 - 0.40 * 1.01, abs=1e-9)
        assert profit > 0

    def test_fee_calculation(self):
        """Verify the BUY_FEE is applied correctly."""
        p_yes = 0.50
        _, profit_yes_win = trade_profit("YES", p_yes, yes_won=True)
        # cost = 0.50 * 1.01 = 0.505
        expected_cost = p_yes * (1.0 + BUY_FEE)
        assert expected_cost == pytest.approx(0.505, abs=1e-9)
        assert profit_yes_win == pytest.approx(1.0 - expected_cost, abs=1e-9)

    def test_price_zero_yes_bet(self):
        """YES bet at price=0: cost = 0, payout = 1 if yes wins."""
        won, profit = trade_profit("YES", 0.0, yes_won=True)
        assert won is True
        assert profit == pytest.approx(1.0, abs=1e-9)

    def test_price_zero_yes_bet_loss(self):
        """YES bet at price=0, NO wins: cost = 0, payout = 0."""
        won, profit = trade_profit("YES", 0.0, yes_won=False)
        assert won is False
        assert profit == pytest.approx(0.0, abs=1e-9)

    def test_price_one_yes_bet(self):
        """YES bet at price=1: cost = 1.01, payout = 1 if yes wins -> small loss (fee)."""
        won, profit = trade_profit("YES", 1.0, yes_won=True)
        assert won is True
        assert profit == pytest.approx(1.0 - 1.0 * 1.01, abs=1e-9)
        assert profit < 0  # Fee makes it a loss even when winning

    def test_price_one_no_bet(self):
        """NO bet at price=1: cost = 0, payout = 1 if NO wins."""
        won, profit = trade_profit("NO", 1.0, yes_won=False)
        assert won is True
        assert profit == pytest.approx(1.0, abs=1e-9)

    def test_price_one_no_bet_loss(self):
        """NO bet at price=1, YES wins: cost = 0, payout = 0."""
        won, profit = trade_profit("NO", 1.0, yes_won=True)
        assert won is False
        assert profit == pytest.approx(0.0, abs=1e-9)

    def test_symmetric_prices(self):
        """At p_yes=0.50, YES and NO bets have equal cost."""
        _, profit_yes = trade_profit("YES", 0.50, yes_won=True)
        _, profit_no = trade_profit("NO", 0.50, yes_won=False)
        assert profit_yes == pytest.approx(profit_no, abs=1e-9)

    def test_buy_fee_constant(self):
        """BUY_FEE should be 0.01 (1%)."""
        assert BUY_FEE == 0.01
