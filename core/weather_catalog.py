"""Build and persist a live catalog of active weather markets."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.client import PolymarketClient
from core.models import Market
from core.weather_market_engine import WeatherMarketEngine, extract_city_phrase
from core.weather_resolution import route_weather_resolution


_WU_PATH_RE = re.compile(r"wunderground\.com/history/daily/([^?#]+)", re.IGNORECASE)


def _yes_no_from_tokens(tokens: List[dict]) -> tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    yes_price = None
    no_price = None
    yes_token = None
    no_token = None
    for token in tokens:
        outcome = str(token.get("outcome", "")).strip().lower()
        token_id = str(token.get("token_id", token.get("tokenId", ""))).strip()
        try:
            price = float(token.get("price", 0))
        except Exception:
            continue
        if outcome == "yes":
            yes_price = price
            yes_token = token_id or None
        elif outcome == "no":
            no_price = price
            no_token = token_id or None
    if yes_price is not None and no_price is None:
        no_price = 1.0 - yes_price
    if no_price is not None and yes_price is None:
        yes_price = 1.0 - no_price
    return yes_price, no_price, yes_token, no_token


def canonicalize_resolution_source(url: Optional[str]) -> Optional[str]:
    raw = str(url or "").strip()
    if not raw:
        return None
    if "wunderground.com/history/daily/" in raw:
        return re.sub(r"/date/[^/?#]+/?$", "", raw)
    return raw


def _country_locality_from_resolution_source(url: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    raw = str(url or "").strip()
    if not raw:
        return None, None
    match = _WU_PATH_RE.search(raw)
    if not match:
        return ("us", None) if "weather.gov" in raw else (None, None)
    parts = [part for part in match.group(1).split("/") if part]
    if len(parts) < 3:
        return None, None
    country = parts[0].lower()
    locality = parts[-2].lower()
    return country, locality


def discover_weather_markets(
    client: PolymarketClient,
    engine: WeatherMarketEngine,
    max_markets: int = 5000,
    page_size: int = 200,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    seen_ids = set()
    while len(seen_ids) < max_markets:
        batch = client.get_markets(
            limit=min(page_size, max_markets - len(seen_ids)),
            active_only=True,
            offset=offset,
            order_by="volume",
            ascending=False,
        )
        if not batch:
            break
        for market in batch:
            if market.condition_id in seen_ids:
                continue
            seen_ids.add(market.condition_id)
            row = build_catalog_entry(market, engine)
            if row is not None:
                rows.append(row)
        if len(batch) < page_size:
            break
        offset += len(batch)
    rows.sort(key=lambda row: (row["country_code"] or "zz", row["city"] or "", -row["volume"], row["question"]))
    return rows


def build_catalog_entry(market: Market, engine: WeatherMarketEngine) -> Optional[Dict[str, Any]]:
    resolution_profile = route_weather_resolution(market.question, market.description, market.resolution_source)
    spec = engine.parse_market(
        market.question,
        description=market.description,
        end_date_iso=market.end_date_iso,
        resolution_source=market.resolution_source,
    )
    # Keep only actual weather markets, not title collisions like "Character of Rain".
    if spec is None and resolution_profile.source_kind == "unknown":
        return None
    if spec is None and not re.search(r"\b(?:highest|lowest)\s+temperature\s+in\b", market.question, re.IGNORECASE):
        return None

    city = None
    canonical_city = None
    station_id = resolution_profile.station_id
    settlement_location_id = resolution_profile.location_id
    settlement_source = resolution_profile.source_kind
    settlement_metric = resolution_profile.settlement_metric
    market_type = None
    contract_type = None
    target_date = None
    target_month = None
    target_year = None
    model_ready = False
    provider_supported = False
    forecast_source = None
    source_country_code, locality_slug = _country_locality_from_resolution_source(market.resolution_source)
    country_code = source_country_code
    if spec is not None:
        city = spec.city or None
        canonical_city = spec.canonical_city or None
        country_code = spec.country_code or country_code
        station_id = spec.station_id or station_id
        settlement_location_id = spec.settlement_location_id or settlement_location_id
        settlement_source = spec.settlement_source
        settlement_metric = spec.settlement_metric
        market_type = spec.market_type
        contract_type = spec.contract_type
        target_date = spec.target_date.isoformat() if spec.target_date else None
        target_month = spec.target_month
        target_year = spec.target_year
        model_ready = bool(spec.city or spec.canonical_city)
        provider = getattr(engine, "provider", None)
        if provider is not None and hasattr(provider, "city_profile"):
            profile = None
            if spec.city:
                profile = provider.city_profile(spec.city, country_code=country_code)
            if profile is None and spec.canonical_city:
                profile = provider.city_profile(spec.canonical_city, country_code=country_code)
            provider_supported = bool(profile)
            if isinstance(profile, dict):
                forecast_source = str(profile.get("forecast_source") or "").strip() or None
        else:
            provider_supported = False
    if city is None:
        city = extract_city_phrase(market.question)
        canonical_city = city
    region_name = canonical_city or city or locality_slug
    region_key = None
    if region_name:
        region_key = f"{(country_code or 'unknown').lower()}:{region_name.lower().replace(' ', '-')}"

    yes_price, no_price, yes_token, no_token = _yes_no_from_tokens(market.tokens)
    return {
        "condition_id": market.condition_id,
        "event_id": market.event_id,
        "question": market.question,
        "slug": market.slug,
        "active": market.active,
        "volume": market.volume,
        "liquidity": market.liquidity,
        "category": market.category,
        "description": market.description,
        "end_date_iso": market.end_date_iso,
        "tags": list(market.tags),
        "city": city,
        "canonical_city": canonical_city,
        "country_code": country_code,
        "locality_slug": locality_slug,
        "region_key": region_key,
        "station_id": station_id,
        "settlement_location_id": settlement_location_id,
        "resolution_source": market.resolution_source,
        "resolution_template": canonicalize_resolution_source(market.resolution_source),
        "settlement_source": settlement_source,
        "settlement_metric": settlement_metric,
        "market_type": market_type,
        "contract_type": contract_type,
        "target_date": target_date,
        "target_month": target_month,
        "target_year": target_year,
        "yes_price": yes_price,
        "no_price": no_price,
        "yes_token_id": yes_token,
        "no_token_id": no_token,
        "model_ready": model_ready,
        "provider_supported": provider_supported,
        "forecast_source": forecast_source if provider_supported else "unmapped",
        "enable_order_book": market.enable_order_book,
    }


def summarize_catalog(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_country: Dict[str, int] = {}
    by_city: Dict[str, int] = {}
    by_region: Dict[str, int] = {}
    supported_regions = 0
    for row in rows:
        country = row.get("country_code") or "unknown"
        by_country[country] = by_country.get(country, 0) + 1
        city = row.get("canonical_city") or row.get("city") or row.get("locality_slug")
        if city:
            by_city[str(city)] = by_city.get(str(city), 0) + 1
        region = row.get("region_key")
        if region:
            by_region[str(region)] = by_region.get(str(region), 0) + 1
        if row.get("provider_supported"):
            supported_regions += 1
    return {
        "count": len(rows),
        "provider_supported_count": supported_regions,
        "countries": dict(sorted(by_country.items(), key=lambda item: (-item[1], item[0]))),
        "cities": dict(sorted(by_city.items(), key=lambda item: (-item[1], item[0]))),
        "regions": dict(sorted(by_region.items(), key=lambda item: (-item[1], item[0]))),
    }


def save_catalog(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summarize_catalog(rows), "markets": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_catalog(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def filter_catalog_rows(
    payload: Dict[str, Any],
    city: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    supported_only: bool = False,
) -> List[Dict[str, Any]]:
    rows = list(payload.get("markets") or [])
    city_filter = str(city or "").strip().lower()
    country_filter = str(country or "").strip().lower()
    region_filter = str(region or "").strip().lower()
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        row_city = str(row.get("canonical_city") or row.get("city") or "").strip().lower()
        row_country = str(row.get("country_code") or "").strip().lower()
        row_region = str(row.get("region_key") or "").strip().lower()
        if supported_only and not bool(row.get("provider_supported")):
            continue
        if city_filter and row_city != city_filter:
            continue
        if country_filter and row_country != country_filter:
            continue
        if region_filter and row_region != region_filter:
            continue
        filtered.append(row)
    return filtered


def _current_token_prices(client: PolymarketClient, rows: List[Dict[str, Any]]) -> Dict[str, float]:
    token_ids = []
    for row in rows:
        for key in ("yes_token_id", "no_token_id"):
            token_id = str(row.get(key) or "").strip()
            if token_id:
                token_ids.append(token_id)
    unique_token_ids = sorted(set(token_ids))
    if not unique_token_ids:
        return {}

    quotes = client.quote_tokens(unique_token_ids)
    executable = client.get_prices([{"token_id": token_id, "side": "BUY"} for token_id in unique_token_ids])
    prices: Dict[str, float] = {}
    for token_id in unique_token_ids:
        quote = quotes.get(token_id, {})
        for key in ("best_ask", "midpoint", "best_bid"):
            raw = quote.get(key)
            if raw is None:
                continue
            try:
                price = float(raw)
            except Exception:
                continue
            if price > 0:
                prices[token_id] = price
                break
        if token_id in prices:
            continue
        side_map = executable.get(token_id, {})
        raw_buy = side_map.get("BUY")
        if raw_buy is None:
            continue
        try:
            price = float(raw_buy)
        except Exception:
            continue
        if price > 0:
            prices[token_id] = price
    return prices


def catalog_rows_to_markets(
    rows: List[Dict[str, Any]],
    client: Optional[PolymarketClient] = None,
    refresh_quotes: bool = True,
) -> List[Market]:
    token_prices = _current_token_prices(client, rows) if client is not None and refresh_quotes else {}
    markets: List[Market] = []
    for row in rows:
        yes_token = str(row.get("yes_token_id") or "").strip()
        no_token = str(row.get("no_token_id") or "").strip()
        yes_price = token_prices.get(yes_token)
        no_price = token_prices.get(no_token)
        if yes_price is None:
            try:
                raw_yes = row.get("yes_price")
                yes_price = None if raw_yes is None else float(raw_yes)
            except Exception:
                yes_price = None
        if no_price is None:
            try:
                raw_no = row.get("no_price")
                no_price = None if raw_no is None else float(raw_no)
            except Exception:
                no_price = None

        tokens: List[Dict[str, Any]] = []
        if yes_token:
            tokens.append({"token_id": yes_token, "outcome": "Yes", "price": str(yes_price if yes_price is not None else 0.0)})
        if no_token:
            tokens.append({"token_id": no_token, "outcome": "No", "price": str(no_price if no_price is not None else 0.0)})

        markets.append(
            Market(
                condition_id=str(row.get("condition_id") or ""),
                question=str(row.get("question") or ""),
                slug=str(row.get("slug") or ""),
                tokens=tokens,
                end_date_iso=row.get("end_date_iso"),
                active=bool(row.get("active", True)),
                volume=float(row.get("volume") or 0.0),
                liquidity=float(row.get("liquidity") or 0.0),
                category=str(row.get("category") or "weather"),
                description=str(row.get("description") or ""),
                resolution_source=row.get("resolution_source"),
                event_id=row.get("event_id"),
                tags=list(row.get("tags") or []),
                enable_order_book=bool(row.get("enable_order_book", False)),
            )
        )
    return markets
