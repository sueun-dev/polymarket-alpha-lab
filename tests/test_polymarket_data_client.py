from unittest.mock import patch

from data.polymarket import PolymarketMarketDataClient


def test_get_markets_mock():
    c = PolymarketMarketDataClient()
    with patch.object(
        c,
        "_fetch_markets",
        return_value=[{"condition_id": "0x1", "question": "Test?", "tokens": [], "active": True}],
    ):
        markets = c.get_markets()
        assert len(markets) == 1
        assert markets[0].condition_id == "0x1"


def test_get_orderbook_mock():
    c = PolymarketMarketDataClient()
    with patch.object(
        c,
        "_fetch_orderbook",
        return_value={"bids": [{"price": "0.49", "size": "100"}], "asks": [{"price": "0.51", "size": "100"}]},
    ):
        book = c.get_orderbook("test_token")
        assert "bids" in book


def test_client_has_no_order_execution_surface():
    c = PolymarketMarketDataClient()
    assert not hasattr(c, "place_order")
    assert not hasattr(c, "get_balance")
    assert not hasattr(c, "get_positions")
