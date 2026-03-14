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


def test_paper_positions_track_buy_and_sell():
    c = PolymarketClient(mode="paper")
    c.place_order(token_id="token-1", side="buy", price=0.50, size=10, market_id="market-1")
    c.place_order(token_id="token-1", side="buy", price=0.60, size=10, market_id="market-1")
    positions = c.get_positions()
    assert len(positions) == 1
    assert positions[0].market_id == "market-1"
    assert positions[0].size == pytest.approx(20.0)
    assert positions[0].entry_price == pytest.approx(0.55)

    c.place_order(token_id="token-1", side="sell", price=0.70, size=5, market_id="market-1")
    positions = c.get_positions()
    assert len(positions) == 1
    assert positions[0].size == pytest.approx(15.0)
    assert positions[0].current_price == pytest.approx(0.70)

    c.place_order(token_id="token-1", side="sell", price=0.72, size=15, market_id="market-1")
    assert c.get_positions() == []

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


def test_get_price_and_midpoint():
    c = PolymarketClient(mode="paper")

    def _get(url, params=None):
        response = MagicMock()
        if url.endswith("/price"):
            response.json.return_value = {"price": "0.51"}
        else:
            response.json.return_value = {"mid": "0.50"}
        response.raise_for_status.return_value = None
        return response

    with patch.object(c._http, "get", side_effect=_get):
        assert c.get_price("token-1", side="buy") == pytest.approx(0.51)
        assert c.get_midpoint("token-1") == pytest.approx(0.50)


def test_get_orderbooks_and_prices_batch():
    c = PolymarketClient(mode="paper")

    def _post(url, json=None):
        response = MagicMock()
        if url.endswith("/books"):
            response.json.return_value = [
                {
                    "asset_id": "token-1",
                    "bids": [{"price": "0.49", "size": "100"}],
                    "asks": [{"price": "0.52", "size": "80"}],
                }
            ]
        else:
            response.json.return_value = {"token-1": {"BUY": "0.52", "SELL": "0.49"}}
        response.raise_for_status.return_value = None
        return response

    with patch.object(c._http, "post", side_effect=_post):
        books = c.get_orderbooks(["token-1"])
        prices = c.get_prices([{"token_id": "token-1", "side": "buy"}])

    assert books[0]["asset_id"] == "token-1"
    assert prices["token-1"]["BUY"] == pytest.approx(0.52)
    summary = PolymarketClient.summarize_orderbook(books[0])
    assert summary["best_bid"] == pytest.approx(0.49)
    assert summary["best_ask"] == pytest.approx(0.52)
    assert summary["spread"] == pytest.approx(0.03)
