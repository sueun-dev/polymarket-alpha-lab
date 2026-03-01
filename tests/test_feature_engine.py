"""Tests for the feature engine -- FeatureRow, build_feature_rows, LiveFeatureBuilder."""
from __future__ import annotations

import math
import statistics
from typing import List, Tuple

import pytest

from data.feature_engine import (
    HORIZONS_MIN,
    FeatureRow,
    LiveFeatureBuilder,
    build_feature_rows,
)
from data.historical_fetcher import MarketSample


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sample(
    close_ts: int = 100_000,
    market_id: str = "mkt-1",
    category: str = "crypto",
    yes_won: bool = True,
) -> MarketSample:
    """Create a minimal MarketSample for testing."""
    return MarketSample(
        market_id=market_id,
        question="Will X happen?",
        category=category,
        close_ts=close_ts,
        yes_token="tok-abc",
        yes_won=yes_won,
    )


def _dense_history(
    start_ts: int,
    end_ts: int,
    step: int = 60,
    price: float = 0.5,
) -> List[Tuple[int, float]]:
    """Return evenly-spaced price history at *price* from *start_ts* to *end_ts*."""
    return [(t, price) for t in range(start_ts, end_ts + 1, step)]


def _ramp_history(
    start_ts: int,
    end_ts: int,
    step: int = 60,
    p_start: float = 0.3,
    p_end: float = 0.7,
) -> List[Tuple[int, float]]:
    """Return a linearly-interpolated price ramp from *p_start* to *p_end*."""
    points = list(range(start_ts, end_ts + 1, step))
    n = len(points)
    if n <= 1:
        return [(start_ts, p_start)]
    return [
        (t, p_start + (p_end - p_start) * i / (n - 1))
        for i, t in enumerate(points)
    ]


# =========================================================================
# FeatureRow dataclass
# =========================================================================

class TestFeatureRow:
    """Basic sanity checks for the FeatureRow dataclass."""

    def test_creation_and_field_access(self) -> None:
        row = FeatureRow(
            market_id="m1",
            close_ts=100,
            horizon_m=5,
            category="sports",
            p=0.6,
            p_minus_5m=0.55,
            p_minus_15m=0.50,
            p_minus_60m=0.40,
            mom5=0.05,
            mom15=0.10,
            mom60=0.20,
            range60=0.15,
            std60=0.04,
            dist_mid=0.10,
            yes_won=True,
        )
        assert row.market_id == "m1"
        assert row.close_ts == 100
        assert row.horizon_m == 5
        assert row.category == "sports"
        assert row.p == 0.6
        assert row.p_minus_5m == 0.55
        assert row.p_minus_15m == 0.50
        assert row.p_minus_60m == 0.40
        assert row.mom5 == 0.05
        assert row.mom15 == 0.10
        assert row.mom60 == 0.20
        assert row.range60 == 0.15
        assert row.std60 == 0.04
        assert row.dist_mid == 0.10
        assert row.yes_won is True

    def test_yes_won_false(self) -> None:
        row = FeatureRow(
            market_id="m2",
            close_ts=200,
            horizon_m=10,
            category="politics",
            p=0.3,
            p_minus_5m=0.35,
            p_minus_15m=0.40,
            p_minus_60m=0.50,
            mom5=-0.05,
            mom15=-0.10,
            mom60=-0.20,
            range60=0.20,
            std60=0.06,
            dist_mid=0.20,
            yes_won=False,
        )
        assert row.yes_won is False

    def test_equality(self) -> None:
        kwargs = dict(
            market_id="m3",
            close_ts=300,
            horizon_m=30,
            category="crypto",
            p=0.5,
            p_minus_5m=0.5,
            p_minus_15m=0.5,
            p_minus_60m=0.5,
            mom5=0.0,
            mom15=0.0,
            mom60=0.0,
            range60=0.0,
            std60=0.0,
            dist_mid=0.0,
            yes_won=True,
        )
        assert FeatureRow(**kwargs) == FeatureRow(**kwargs)


# =========================================================================
# HORIZONS_MIN constant
# =========================================================================

class TestHorizonsMin:
    def test_values(self) -> None:
        assert HORIZONS_MIN == (5, 10, 15, 30, 60, 120)

    def test_immutable(self) -> None:
        assert isinstance(HORIZONS_MIN, tuple)


# =========================================================================
# build_feature_rows
# =========================================================================

class TestBuildFeatureRows:
    """Tests for the module-level build_feature_rows function."""

    def test_empty_history_returns_empty(self) -> None:
        sample = _make_sample(close_ts=100_000)
        assert build_feature_rows(sample, []) == []

    def test_complete_history_produces_all_horizons(self) -> None:
        """Dense history covering well beyond the largest horizon should yield
        a row for every horizon in HORIZONS_MIN."""
        close_ts = 100_000
        # Need data from close_ts - 120*60 (entry) - 60*60 (lookback) onward.
        # That's close_ts - 180*60 = close_ts - 10800.
        start = close_ts - 200 * 60  # generous padding
        history = _dense_history(start, close_ts, step=60, price=0.5)
        sample = _make_sample(close_ts=close_ts)

        rows = build_feature_rows(sample, history)

        horizons_found = {r.horizon_m for r in rows}
        assert horizons_found == set(HORIZONS_MIN)

    def test_missing_price_skips_horizon(self) -> None:
        """If the history does not extend far enough back to cover the 60-min
        lookback for a given horizon, that horizon must be skipped."""
        close_ts = 100_000
        # Only provide data starting at close_ts - 30*60.
        # The 5-min horizon entry_ts = close_ts - 5*60 = close_ts - 300
        # Needs price at entry_ts - 60*60 = close_ts - 300 - 3600 = close_ts - 3900.
        # We start at close_ts - 1800, so missing p60 for all horizons.
        start = close_ts - 30 * 60
        history = _dense_history(start, close_ts, step=60, price=0.5)
        sample = _make_sample(close_ts=close_ts)

        rows = build_feature_rows(sample, history)
        assert rows == []

    def test_price_outside_0_1_skipped(self) -> None:
        """Prices outside [0, 1] should cause the horizon to be skipped."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        # Build history with an out-of-range price at the entry point for
        # the 5-min horizon.
        history = _dense_history(start, close_ts, step=60, price=0.5)
        entry_5 = close_ts - 5 * 60  # entry for the 5-min horizon
        # Replace entry point with invalid price
        history = [(t, 1.5 if t == entry_5 else p) for t, p in history]

        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)

        # 5-min horizon should be skipped; others remain.
        horizons = {r.horizon_m for r in rows}
        assert 5 not in horizons
        # Other horizons unaffected.
        assert len(horizons) == len(HORIZONS_MIN) - 1

    def test_negative_price_skipped(self) -> None:
        """Negative prices should also be skipped."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _dense_history(start, close_ts, step=60, price=0.5)
        entry_10 = close_ts - 10 * 60
        # Make the 15-min lookback price negative for the 10-min horizon entry.
        target_ts = entry_10 - 15 * 60
        history = [(t, -0.1 if t == target_ts else p) for t, p in history]

        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)
        horizons = {r.horizon_m for r in rows}
        assert 10 not in horizons

    def test_window_fewer_than_4_prices_skipped(self) -> None:
        """If the 60-min window has fewer than 4 data points the horizon
        must be skipped."""
        close_ts = 100_000
        # Provide only 3 data points in the 60-min window for the 5-min horizon.
        entry_5 = close_ts - 5 * 60
        # We need prices at entry, entry-5m, entry-15m, entry-60m.
        # Window is [entry-60m, entry].
        pts = [
            (entry_5 - 60 * 60, 0.4),  # p60
            (entry_5 - 15 * 60, 0.45),  # p15
            (entry_5 - 5 * 60, 0.48),  # p5
            (entry_5, 0.50),  # p
        ]
        # Window [entry-3600, entry] has 4 points.  Remove one to get 3.
        sparse_pts = [pts[0], pts[2], pts[3]]  # drop the 15-min point

        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, sparse_pts)
        # The p15 lookup should still work (it returns the closest earlier),
        # but the window now has only 3 points, so the horizon is skipped.
        horizons = {r.horizon_m for r in rows}
        assert 5 not in horizons

    def test_momentum_values(self) -> None:
        """Verify that momentum fields equal p - p_minus_Xm."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        # Use a ramp so prices differ at each lookback.
        history = _ramp_history(start, close_ts, step=60, p_start=0.3, p_end=0.7)
        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)

        for row in rows:
            assert row.mom5 == pytest.approx(row.p - row.p_minus_5m)
            assert row.mom15 == pytest.approx(row.p - row.p_minus_15m)
            assert row.mom60 == pytest.approx(row.p - row.p_minus_60m)

    def test_range60_calculation(self) -> None:
        """range60 must equal max(window) - min(window) for the 60-min window."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        # Construct history where values oscillate between 0.4 and 0.6.
        history: List[Tuple[int, float]] = []
        for t in range(start, close_ts + 1, 60):
            # Alternate high/low
            p = 0.6 if ((t - start) // 60) % 2 == 0 else 0.4
            history.append((t, p))

        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)
        assert len(rows) > 0
        for row in rows:
            assert row.range60 == pytest.approx(0.2)

    def test_std60_calculation(self) -> None:
        """std60 must equal statistics.pstdev of the window prices."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _ramp_history(start, close_ts, step=60, p_start=0.3, p_end=0.7)
        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)

        # Manually compute expected std60 for the 5-min horizon.
        entry_ts_5 = close_ts - 5 * 60
        win_prices = [p for t, p in history if entry_ts_5 - 60 * 60 <= t <= entry_ts_5]
        expected_std = statistics.pstdev(win_prices)

        row_5 = [r for r in rows if r.horizon_m == 5]
        assert len(row_5) == 1
        assert row_5[0].std60 == pytest.approx(expected_std)

    def test_dist_mid_calculation(self) -> None:
        """dist_mid must equal abs(p - 0.5)."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _dense_history(start, close_ts, step=60, price=0.7)
        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)
        for row in rows:
            assert row.dist_mid == pytest.approx(abs(row.p - 0.5))

    def test_sample_fields_propagated(self) -> None:
        """market_id, close_ts, category, yes_won come from the sample."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _dense_history(start, close_ts, step=60, price=0.5)
        sample = _make_sample(
            close_ts=close_ts, market_id="xyz", category="politics", yes_won=False
        )
        rows = build_feature_rows(sample, history)
        for row in rows:
            assert row.market_id == "xyz"
            assert row.close_ts == close_ts
            assert row.category == "politics"
            assert row.yes_won is False

    def test_flat_price_zero_momentum(self) -> None:
        """A perfectly flat price history should yield zero momentum."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _dense_history(start, close_ts, step=60, price=0.5)
        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)
        for row in rows:
            assert row.mom5 == pytest.approx(0.0)
            assert row.mom15 == pytest.approx(0.0)
            assert row.mom60 == pytest.approx(0.0)
            assert row.range60 == pytest.approx(0.0)
            assert row.std60 == pytest.approx(0.0)

    def test_boundary_price_zero_accepted(self) -> None:
        """A price of exactly 0.0 is within [0, 1] and should be accepted."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _dense_history(start, close_ts, step=60, price=0.0)
        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)
        assert len(rows) == len(HORIZONS_MIN)

    def test_boundary_price_one_accepted(self) -> None:
        """A price of exactly 1.0 is within [0, 1] and should be accepted."""
        close_ts = 100_000
        start = close_ts - 200 * 60
        history = _dense_history(start, close_ts, step=60, price=1.0)
        sample = _make_sample(close_ts=close_ts)
        rows = build_feature_rows(sample, history)
        assert len(rows) == len(HORIZONS_MIN)


# =========================================================================
# LiveFeatureBuilder
# =========================================================================

class TestLiveFeatureBuilder:
    """Tests for the LiveFeatureBuilder provider."""

    def _builder(self) -> LiveFeatureBuilder:
        return LiveFeatureBuilder()

    def test_name(self) -> None:
        assert self._builder().name == "feature_engine"

    # ----- compute_live_features -----

    def test_compute_live_features_normal(self) -> None:
        """With dense data, compute_live_features should return a dict with
        all expected keys and correct values."""
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _dense_history(start, current_ts, step=60, price=0.65)

        result = builder.compute_live_features(prices, current_ts)
        assert result is not None
        assert set(result.keys()) == {"p", "mom5", "mom15", "mom60", "range60", "std60", "dist_mid"}
        assert result["p"] == pytest.approx(0.65)
        assert result["mom5"] == pytest.approx(0.0)
        assert result["mom15"] == pytest.approx(0.0)
        assert result["mom60"] == pytest.approx(0.0)
        assert result["range60"] == pytest.approx(0.0)
        assert result["std60"] == pytest.approx(0.0)
        assert result["dist_mid"] == pytest.approx(0.15)

    def test_compute_live_features_ramp(self) -> None:
        """With a price ramp, momentum values should be positive."""
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _ramp_history(start, current_ts, step=60, p_start=0.3, p_end=0.7)

        result = builder.compute_live_features(prices, current_ts)
        assert result is not None
        assert result["mom5"] > 0
        assert result["mom15"] > 0
        assert result["mom60"] > 0
        assert result["range60"] > 0
        assert result["std60"] > 0

    def test_compute_live_features_insufficient_data_empty(self) -> None:
        """Empty price list must return None."""
        builder = self._builder()
        assert builder.compute_live_features([], 100_000) is None

    def test_compute_live_features_insufficient_data_no_lookback(self) -> None:
        """If history only covers recent seconds, momentum lookbacks fail."""
        builder = self._builder()
        current_ts = 100_000
        # Only 2 minutes of data -- not enough for 5-min momentum.
        prices = _dense_history(current_ts - 120, current_ts, step=60, price=0.5)
        assert builder.compute_live_features(prices, current_ts) is None

    def test_compute_live_features_insufficient_window_prices(self) -> None:
        """If the 60-min window has fewer than 4 prices, return None."""
        builder = self._builder()
        current_ts = 100_000
        # Provide data that satisfies momentum lookbacks but has only 3
        # points in the 60-min window.
        prices = [
            (current_ts - 70 * 60, 0.5),   # outside window (for 60-min momentum)
            (current_ts - 50 * 60, 0.5),    # inside window
            (current_ts - 30 * 60, 0.5),    # inside window
            (current_ts, 0.5),              # inside window (only 3 in window)
        ]
        assert builder.compute_live_features(prices, current_ts) is None

    def test_compute_live_features_via_fetch(self) -> None:
        """The fetch() method should delegate to compute_live_features."""
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _dense_history(start, current_ts, step=60, price=0.5)

        result = builder.fetch(prices=prices, current_ts=current_ts)
        assert result is not None
        assert result["p"] == pytest.approx(0.5)

    def test_fetch_no_args_returns_none(self) -> None:
        """fetch() with no arguments should return None (empty prices)."""
        builder = self._builder()
        assert builder.fetch() is None

    # ----- compute_momentum -----

    def test_compute_momentum_normal(self) -> None:
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _ramp_history(start, current_ts, step=60, p_start=0.3, p_end=0.7)

        mom = builder.compute_momentum(prices, current_ts, 5)
        assert mom is not None
        assert mom > 0  # price is rising

    def test_compute_momentum_flat(self) -> None:
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _dense_history(start, current_ts, step=60, price=0.5)

        mom = builder.compute_momentum(prices, current_ts, 5)
        assert mom is not None
        assert mom == pytest.approx(0.0)

    def test_compute_momentum_no_current_price(self) -> None:
        """If there is no price at or before current_ts, return None."""
        builder = self._builder()
        # All data is in the future relative to current_ts.
        prices = [(200_000, 0.5), (200_060, 0.6)]
        assert builder.compute_momentum(prices, 100_000, 5) is None

    def test_compute_momentum_no_lookback_price(self) -> None:
        """If there is no price at the lookback point, return None."""
        builder = self._builder()
        current_ts = 100_000
        # Only 1 minute of data; 5-min lookback impossible.
        prices = [(current_ts - 60, 0.5), (current_ts, 0.5)]
        assert builder.compute_momentum(prices, current_ts, 5) is None

    def test_compute_momentum_exact_values(self) -> None:
        """Verify momentum is exactly p_now - p_past."""
        builder = self._builder()
        current_ts = 100_000
        prices = [
            (current_ts - 5 * 60, 0.40),
            (current_ts, 0.55),
        ]
        mom = builder.compute_momentum(prices, current_ts, 5)
        assert mom == pytest.approx(0.15)

    # ----- compute_volatility -----

    def test_compute_volatility_normal(self) -> None:
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _ramp_history(start, current_ts, step=60, p_start=0.3, p_end=0.7)

        vol = builder.compute_volatility(prices, current_ts, 60)
        assert vol is not None
        assert vol > 0

    def test_compute_volatility_matches_pstdev(self) -> None:
        """Verify the volatility equals statistics.pstdev of window prices."""
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _ramp_history(start, current_ts, step=60, p_start=0.3, p_end=0.7)

        vol = builder.compute_volatility(prices, current_ts, 60)
        # Manually compute.
        win = [p for t, p in prices if current_ts - 60 * 60 <= t <= current_ts]
        expected = statistics.pstdev(win)
        assert vol == pytest.approx(expected)

    def test_compute_volatility_flat_is_zero(self) -> None:
        builder = self._builder()
        current_ts = 100_000
        start = current_ts - 200 * 60
        prices = _dense_history(start, current_ts, step=60, price=0.5)

        vol = builder.compute_volatility(prices, current_ts, 60)
        assert vol == pytest.approx(0.0)

    def test_compute_volatility_empty_window(self) -> None:
        """If no data points exist in the window, return None."""
        builder = self._builder()
        # All data is well outside the 60-min window.
        prices = [(50_000, 0.5)]
        assert builder.compute_volatility(prices, 100_000, 60) is None

    def test_compute_volatility_single_point(self) -> None:
        """A single point in the window yields fewer than 2 prices -> None."""
        builder = self._builder()
        current_ts = 100_000
        prices = [(current_ts, 0.5)]
        assert builder.compute_volatility(prices, current_ts, 60) is None

    def test_compute_volatility_custom_window(self) -> None:
        """A shorter window should only consider prices in that range."""
        builder = self._builder()
        current_ts = 100_000
        prices = [
            (current_ts - 30 * 60, 0.40),
            (current_ts - 20 * 60, 0.50),
            (current_ts - 10 * 60, 0.60),
            (current_ts, 0.50),
        ]
        vol_30 = builder.compute_volatility(prices, current_ts, 30)
        expected = statistics.pstdev([0.40, 0.50, 0.60, 0.50])
        assert vol_30 == pytest.approx(expected)

        # Only the last 3 points are within a 20-min window.
        vol_20 = builder.compute_volatility(prices, current_ts, 20)
        expected_20 = statistics.pstdev([0.50, 0.60, 0.50])
        assert vol_20 == pytest.approx(expected_20)

    # ----- caching from BaseDataProvider -----

    def test_inherits_base_provider(self) -> None:
        from data.base_provider import BaseDataProvider

        builder = self._builder()
        assert isinstance(builder, BaseDataProvider)

    def test_cache_methods_available(self) -> None:
        builder = self._builder()
        builder.set_cached("test_key", {"val": 42})
        assert builder.get_cached("test_key") == {"val": 42}
