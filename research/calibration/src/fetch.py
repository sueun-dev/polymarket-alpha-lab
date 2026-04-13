"""Polymarket Gamma API에서 resolved 마켓 데이터를 수집."""

import json
import time
from pathlib import Path

import requests

GAMMA_URL = "https://gamma-api.polymarket.com"
MARKETS_ENDPOINT = f"{GAMMA_URL}/markets"
CLOB_URL = "https://clob.polymarket.com"
PRICES_HISTORY_ENDPOINT = f"{CLOB_URL}/prices-history"

# API 파라미터
BATCH_SIZE = 100
RATE_LIMIT_DELAY = 0.3
PRICE_HISTORY_DELAY = 0.15


def fetch_resolved_markets(
    max_markets: int = 5000,
    min_volume: float = 1000.0,
) -> list[dict]:
    """Resolved된 바이너리 마켓을 수집한다.

    Args:
        max_markets: 수집할 최대 마켓 수.
        min_volume: 최소 거래량 필터 (USD).

    Returns:
        resolved 마켓 딕셔너리 리스트.
    """
    all_markets = []
    offset = 0

    print(f"Fetching resolved markets (max={max_markets}, min_volume=${min_volume})...")

    while len(all_markets) < max_markets:
        params = {
            "closed": True,
            "limit": BATCH_SIZE,
            "offset": offset,
            "order": "volume",
            "ascending": False,
        }

        try:
            resp = requests.get(MARKETS_ENDPOINT, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  API request failed at offset {offset}: {e}")
            break

        batch = resp.json()
        if not batch:
            print(f"  No more markets at offset {offset}. Done.")
            break

        for market in batch:
            if _is_valid_resolved_binary(market, min_volume):
                all_markets.append(_extract_fields(market))

        print(f"  Fetched offset={offset}, batch={len(batch)}, total_valid={len(all_markets)}")
        offset += BATCH_SIZE
        time.sleep(RATE_LIMIT_DELAY)

    print(f"Total resolved binary markets collected: {len(all_markets)}")

    # 각 마켓의 resolve 직전 가격을 가져옴
    print(f"\nFetching pre-resolution prices for {len(all_markets)} markets...")
    _enrich_with_pre_resolution_prices(all_markets)

    return all_markets


def _is_valid_resolved_binary(market: dict, min_volume: float) -> bool:
    """마켓이 resolved된 바이너리 마켓인지 확인."""
    if not market.get("closed"):
        return False

    # outcomePrices로 resolve 여부 확인 (settlement가 0/1)
    outcome_prices = market.get("outcomePrices")
    if not outcome_prices:
        return False
    try:
        prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
        p0 = float(prices[0])
        # settlement: Yes 가격이 정확히 0 또는 1이어야 resolved
        if p0 not in (0.0, 1.0):
            # 거의 0 또는 1에 근접한 경우도 허용
            if not (p0 <= 0.001 or p0 >= 0.999):
                return False
    except (json.JSONDecodeError, TypeError, IndexError, ValueError):
        return False

    # 바이너리 마켓만 (outcomes가 Yes/No 2개)
    outcomes = market.get("outcomes")
    if not outcomes:
        return False
    try:
        outcomes_list = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        if set(outcomes_list) != {"Yes", "No"}:
            return False
    except (json.JSONDecodeError, TypeError):
        return False

    # 최소 거래량
    try:
        volume = float(market.get("volume", 0))
    except (ValueError, TypeError):
        return False

    if volume < min_volume:
        return False

    return True


def _extract_fields(market: dict) -> dict:
    """마켓에서 분석에 필요한 필드만 추출."""
    outcome_prices = market.get("outcomePrices", "")
    try:
        prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
        p0 = float(prices[0])
        # settlement price로 실제 결과 판단
        resolved_yes = p0 >= 0.999
    except (json.JSONDecodeError, TypeError, IndexError, ValueError):
        resolved_yes = None

    # clobTokenIds 추출 (price history 용)
    clob_token_ids = market.get("clobTokenIds", "[]")
    try:
        token_ids = json.loads(clob_token_ids) if isinstance(clob_token_ids, str) else clob_token_ids
    except (json.JSONDecodeError, TypeError):
        token_ids = []

    return {
        "condition_id": market.get("conditionId", ""),
        "question": market.get("question", ""),
        "outcome": "Yes" if resolved_yes else "No",
        "outcome_binary": 1 if resolved_yes else 0,
        "yes_price": None,  # pre-resolution price — enriched later
        "volume": float(market.get("volume", 0)),
        "end_date": market.get("endDate", ""),
        "resolved_at": market.get("closedTime", market.get("resolvedAt", "")),
        "category": market.get("category", ""),
        "tags": market.get("tags", []),
        "slug": market.get("slug", ""),
        "yes_token_id": token_ids[0] if token_ids else "",
    }


def _enrich_with_pre_resolution_prices(markets: list[dict]):
    """각 마켓에 resolve 직전 가격을 추가."""
    success = 0
    fail = 0

    for i, market in enumerate(markets):
        token_id = market.get("yes_token_id", "")
        if not token_id:
            fail += 1
            continue

        price = _get_pre_resolution_price(token_id)
        if price is not None:
            market["yes_price"] = price
            success += 1
        else:
            fail += 1

        if (i + 1) % 50 == 0:
            print(f"  Price history: {i+1}/{len(markets)} (success={success}, fail={fail})")

        time.sleep(PRICE_HISTORY_DELAY)

    print(f"  Price enrichment done: {success} success, {fail} failed")


def _get_pre_resolution_price(token_id: str) -> float | None:
    """CLOB API에서 resolve 직전 가격을 가져온다.

    전략:
    1. fidelity=1440 (daily) 부터 시도 (대부분 마켓에서 동작)
    2. 마지막 non-settlement 가격을 사용하되, resolve 시점에서 7일 이내만 허용
    """
    for fidelity in [1440, 60]:
        try:
            resp = requests.get(
                PRICES_HISTORY_ENDPOINT,
                params={"market": token_id, "interval": "max", "fidelity": fidelity},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException:
            continue

        history = resp.json().get("history", [])
        if not history:
            continue

        last_timestamp = history[-1].get("t", 0)
        max_age_seconds = 7 * 24 * 3600  # 7일

        # 뒤에서부터 탐색: non-settlement + 7일 이내
        for point in reversed(history):
            p = float(point.get("p", 0))
            t = point.get("t", 0)
            age = last_timestamp - t
            if age > max_age_seconds:
                break
            if 0.02 < p < 0.98:
                return round(p, 4)

        # 넓은 범위로 재시도 (여전히 7일 제한)
        for point in reversed(history):
            p = float(point.get("p", 0))
            t = point.get("t", 0)
            age = last_timestamp - t
            if age > max_age_seconds:
                break
            if 0.005 < p < 0.995:
                return round(p, 4)

    return None


def save_raw_data(markets: list[dict], output_path: str = "data/resolved_markets.json"):
    """수집된 데이터를 JSON으로 저장."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(markets, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(markets)} markets to {path}")


def load_raw_data(input_path: str = "data/resolved_markets.json") -> list[dict]:
    """저장된 JSON 데이터를 로드."""
    with open(input_path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    markets = fetch_resolved_markets()
    save_raw_data(markets)
