# tests/test_scanner.py
import pytest
from unittest.mock import MagicMock
from core.scanner import MarketScanner
from core.models import Market

def test_filter_by_volume():
    client = MagicMock()
    client.get_markets.return_value = [
        Market(condition_id="0x1", question="Q1", tokens=[], volume=5000),
        Market(condition_id="0x2", question="Q2", tokens=[], volume=100),
    ]
    scanner = MarketScanner(client=client, min_volume=1000)
    assert len(scanner.scan()) == 1

def test_filter_inactive():
    client = MagicMock()
    client.get_markets.return_value = [
        Market(condition_id="0x1", question="Q1", tokens=[], active=True, volume=5000),
        Market(condition_id="0x2", question="Q2", tokens=[], active=False, volume=5000),
    ]
    scanner = MarketScanner(client=client, min_volume=0)
    assert len(scanner.scan()) == 1

def test_price_spike():
    scanner = MarketScanner(client=MagicMock(), min_volume=0)
    assert scanner.is_price_spike(0.50, 0.70, 0.15) is True
    assert scanner.is_price_spike(0.50, 0.55, 0.15) is False

def test_price_cache():
    scanner = MarketScanner(client=MagicMock(), min_volume=0)
    assert scanner.update_price_cache("m1", 0.50) is None
    assert scanner.update_price_cache("m1", 0.65) == 0.50
