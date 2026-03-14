from __future__ import annotations

from core.models import Market
from core.weather_catalog import catalog_rows_to_markets, filter_catalog_rows


class _FakeClient:
    def quote_tokens(self, token_ids):
        return {
            "yes-1": {"best_ask": 0.12},
            "no-1": {"best_ask": 0.88},
        }

    def get_prices(self, requests):
        return {}


def test_filter_catalog_rows_respects_supported_city_and_country() -> None:
    payload = {
        "markets": [
            {
                "condition_id": "a",
                "canonical_city": "atlanta",
                "country_code": "us",
                "region_key": "us:atlanta",
                "provider_supported": True,
            },
            {
                "condition_id": "b",
                "canonical_city": "seoul",
                "country_code": "kr",
                "region_key": "kr:seoul",
                "provider_supported": False,
            },
        ]
    }

    filtered = filter_catalog_rows(payload, city="atlanta", country="us", supported_only=True)

    assert len(filtered) == 1
    assert filtered[0]["condition_id"] == "a"


def test_catalog_rows_to_markets_uses_live_quote_prices() -> None:
    rows = [
        {
            "condition_id": "0x1",
            "question": "Will it rain in Atlanta on March 11?",
            "slug": "rain-atlanta",
            "active": True,
            "volume": 1000,
            "liquidity": 500,
            "category": "weather",
            "description": "Resolution source: https://example.com",
            "end_date_iso": "2026-03-11T23:59:59Z",
            "resolution_source": "https://example.com",
            "event_id": "evt-1",
            "tags": ["weather"],
            "yes_price": 0.2,
            "no_price": 0.8,
            "yes_token_id": "yes-1",
            "no_token_id": "no-1",
            "enable_order_book": True,
        }
    ]

    markets = catalog_rows_to_markets(rows, client=_FakeClient(), refresh_quotes=True)

    assert len(markets) == 1
    market = markets[0]
    assert isinstance(market, Market)
    assert market.tokens[0]["price"] == "0.12"
    assert market.tokens[1]["price"] == "0.88"
