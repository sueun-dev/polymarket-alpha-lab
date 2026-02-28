# tests/test_client.py
import pytest
from unittest.mock import patch, MagicMock
from core.client import PolymarketClient

def test_paper_mode():
    c = PolymarketClient(mode="paper")
    assert c.is_live is False

def test_paper_balance():
    c = PolymarketClient(mode="paper", paper_balance=10000.0)
    assert c.get_balance() == 10000.0

def test_paper_order():
    c = PolymarketClient(mode="paper")
    order = c.place_order(token_id="test", side="buy", price=0.50, size=10)
    assert order.status == "paper"
    assert c.get_balance() == 10000.0 - 5.0

def test_get_markets_mock():
    c = PolymarketClient(mode="paper")
    with patch.object(c, '_fetch_markets', return_value=[{"condition_id": "0x1", "question": "Test?", "tokens": [], "active": True}]):
        markets = c.get_markets()
        assert len(markets) == 1
        assert markets[0].condition_id == "0x1"

def test_get_orderbook_mock():
    c = PolymarketClient(mode="paper")
    with patch.object(c, '_fetch_orderbook', return_value={"bids": [{"price": "0.49", "size": "100"}], "asks": [{"price": "0.51", "size": "100"}]}):
        book = c.get_orderbook("test_token")
        assert "bids" in book
