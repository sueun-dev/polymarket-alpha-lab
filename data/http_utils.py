"""HTTP helpers and safe-parsing utilities for data providers."""
from __future__ import annotations

import datetime as dt
import json
import math
import time
import urllib.error
import urllib.request
from typing import List, Optional

USER_AGENT = "polymarket-data/1.0"


def http_get_json(url: str, retries: int = 3, timeout: int = 20) -> object:
    """HTTP GET that returns decoded JSON, with retries and exponential backoff."""
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
        ) as err:
            last_err = err
            if attempt >= retries:
                break
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"request failed: {url} ({last_err})")


def parse_float(value: object) -> Optional[float]:
    """Safe float parsing with NaN/Inf protection.  Returns *None* on failure."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(v):
        return v
    return None


def parse_close_ts(value: object) -> Optional[int]:
    """Parse various timestamp formats to a Unix-epoch int (seconds)."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None

    candidates = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]

    for fmt in candidates:
        try:
            d = dt.datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return int(d.timestamp())
        except ValueError:
            pass

    # fallback: normalize +00 -> +00:00
    if s.endswith("+00"):
        s = s + ":00"
    try:
        d2 = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d2.tzinfo is None:
            d2 = d2.replace(tzinfo=dt.timezone.utc)
        return int(d2.timestamp())
    except ValueError:
        return None


def parse_json_array(value: object) -> List[object]:
    """Safe JSON array parsing from string or list.  Returns ``[]`` on failure."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []
