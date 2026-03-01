"""Bridge between HistoricalFetcher data and BacktestEngine format."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from backtest.data_loader import HistoricalDataPoint
from core.models import Market
from data.historical_fetcher import HistoricalFetcher, MarketSample

BUY_FEE = 0.01


class BacktestDataBuilder:
    """Convert historical Polymarket data into backtest-ready format."""

    def __init__(self, fetcher: Optional[HistoricalFetcher] = None) -> None:
        self.fetcher = fetcher or HistoricalFetcher()

    def samples_to_data_points(
        self,
        samples: List[MarketSample],
        histories: dict[str, List[Tuple[int, float]]],
    ) -> List[HistoricalDataPoint]:
        """Convert MarketSamples + price histories into HistoricalDataPoints.

        For each sample, uses the price history to create data points at multiple
        timestamps (at each horizon before close).  This gives the backtest engine
        a time-series of market states to iterate through.
        """
        data_points: List[HistoricalDataPoint] = []
        for sample in samples:
            history = histories.get(sample.yes_token, [])
            if not history:
                continue

            # Create data points at key timestamps (at each horizon before close)
            for horizon_minutes in (5, 15, 30, 60, 120):
                ts = sample.close_ts - horizon_minutes * 60
                # Find price at this timestamp
                yes_price = HistoricalFetcher.price_at_or_before(history, ts)
                if yes_price is None:
                    continue
                no_price = 1.0 - yes_price

                market = Market(
                    condition_id=sample.market_id,
                    question=sample.question,
                    tokens=[
                        {
                            "token_id": f"{sample.market_id}_yes",
                            "outcome": "Yes",
                            "price": str(yes_price),
                        },
                        {
                            "token_id": f"{sample.market_id}_no",
                            "outcome": "No",
                            "price": str(no_price),
                        },
                    ],
                    volume=0.0,
                    category=sample.category,
                )

                dp = HistoricalDataPoint(
                    timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                    market=market,
                    yes_price=yes_price,
                    no_price=no_price,
                    volume=0.0,
                )
                data_points.append(dp)

        data_points.sort(key=lambda x: x.timestamp)
        return data_points

    def export_csv(
        self, data_points: List[HistoricalDataPoint], output_path: str
    ) -> int:
        """Export data points as CSV for the existing backtest loader.

        Returns the number of rows written.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["timestamp", "condition_id", "question", "yes_price", "no_price", "volume"]
            )
            for dp in data_points:
                writer.writerow(
                    [
                        dp.timestamp.isoformat(),
                        dp.market.condition_id,
                        dp.market.question,
                        f"{dp.yes_price:.6f}",
                        f"{dp.no_price:.6f}",
                        f"{dp.volume:.2f}",
                    ]
                )
                count += 1

        return count

    def split_train_test(
        self,
        data_points: List[HistoricalDataPoint],
        train_ratio: float = 0.7,
    ) -> Tuple[List[HistoricalDataPoint], List[HistoricalDataPoint]]:
        """Chronological train/test split."""
        if not data_points:
            return [], []
        idx = int(len(data_points) * train_ratio)
        idx = max(1, min(idx, len(data_points) - 1))
        return data_points[:idx], data_points[idx:]


def trade_profit(side: str, p_yes: float, yes_won: bool) -> Tuple[bool, float]:
    """Calculate profit/loss for a trade.

    Args:
        side: "YES" or "NO"
        p_yes: YES price at time of trade
        yes_won: whether YES resolved as winner

    Returns:
        Tuple of (won: bool, profit: float)
    """
    if side == "YES":
        cost = p_yes * (1.0 + BUY_FEE)
        won = yes_won
    else:
        cost = (1.0 - p_yes) * (1.0 + BUY_FEE)
        won = not yes_won
    payout = 1.0 if won else 0.0
    return won, payout - cost
