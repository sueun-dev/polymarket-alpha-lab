import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional
from core.models import Market

class HistoricalDataPoint:
    def __init__(self, timestamp: datetime, market: Market, yes_price: float, no_price: float, volume: float):
        self.timestamp = timestamp
        self.market = market
        self.yes_price = yes_price
        self.no_price = no_price
        self.volume = volume

class DataLoader:
    def load_csv(self, filepath: str) -> list[HistoricalDataPoint]:
        """Load historical data from CSV: timestamp,condition_id,question,yes_price,no_price,volume"""
        data = []
        path = Path(filepath)
        if not path.exists():
            return data
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                market = Market(condition_id=row["condition_id"], question=row.get("question", ""), tokens=[
                    {"token_id": f"{row['condition_id']}_yes", "outcome": "Yes", "price": row["yes_price"]},
                    {"token_id": f"{row['condition_id']}_no", "outcome": "No", "price": row["no_price"]},
                ], volume=float(row.get("volume", 0)))
                dp = HistoricalDataPoint(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    market=market,
                    yes_price=float(row["yes_price"]),
                    no_price=float(row["no_price"]),
                    volume=float(row.get("volume", 0)),
                )
                data.append(dp)
        return data

    def load_json(self, filepath: str) -> list[HistoricalDataPoint]:
        """Load from JSON array of objects"""
        data = []
        path = Path(filepath)
        if not path.exists():
            return data
        with open(path) as f:
            records = json.load(f)
        for row in records:
            market = Market(condition_id=row["condition_id"], question=row.get("question", ""), tokens=[
                {"token_id": f"{row['condition_id']}_yes", "outcome": "Yes", "price": str(row["yes_price"])},
                {"token_id": f"{row['condition_id']}_no", "outcome": "No", "price": str(row["no_price"])},
            ], volume=float(row.get("volume", 0)))
            dp = HistoricalDataPoint(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                market=market,
                yes_price=float(row["yes_price"]),
                no_price=float(row["no_price"]),
                volume=float(row.get("volume", 0)),
            )
            data.append(dp)
        return data
