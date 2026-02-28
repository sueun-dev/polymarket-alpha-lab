"""Tests for data.http_utils and data.base_provider."""
from __future__ import annotations

import io
import json
import math
import time
import urllib.error
from typing import Any
from unittest import mock

import pytest

from data.http_utils import http_get_json, parse_close_ts, parse_float, parse_json_array
from data.base_provider import BaseDataProvider


# ---------------------------------------------------------------------------
# http_get_json
# ---------------------------------------------------------------------------


class TestHttpGetJson:
    """Tests for retry logic and JSON decoding."""

    def _mock_urlopen(self, body: bytes, *, status: int = 200):
        """Return a context-manager mock that behaves like urlopen."""
        resp = mock.MagicMock()
        resp.read.return_value = body
        resp.__enter__ = mock.MagicMock(return_value=resp)
        resp.__exit__ = mock.MagicMock(return_value=False)
        return resp

    @mock.patch("data.http_utils.urllib.request.urlopen")
    def test_success_first_try(self, mock_urlopen):
        payload = {"key": "value"}
        mock_urlopen.return_value = self._mock_urlopen(json.dumps(payload).encode())
        result = http_get_json("https://example.com/api")
        assert result == payload
        assert mock_urlopen.call_count == 1

    @mock.patch("data.http_utils.time.sleep")
    @mock.patch("data.http_utils.urllib.request.urlopen")
    def test_retries_on_url_error(self, mock_urlopen, mock_sleep):
        payload = {"ok": True}
        mock_urlopen.side_effect = [
            urllib.error.URLError("network down"),
            self._mock_urlopen(json.dumps(payload).encode()),
        ]
        result = http_get_json("https://example.com/api", retries=3)
        assert result == payload
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once_with(0.4)

    @mock.patch("data.http_utils.time.sleep")
    @mock.patch("data.http_utils.urllib.request.urlopen")
    def test_exhausts_retries_then_raises(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = urllib.error.URLError("always fails")
        with pytest.raises(RuntimeError, match="request failed"):
            http_get_json("https://example.com/api", retries=2)
        # initial attempt + 2 retries = 3 total
        assert mock_urlopen.call_count == 3

    @mock.patch("data.http_utils.time.sleep")
    @mock.patch("data.http_utils.urllib.request.urlopen")
    def test_exponential_backoff_sleeps(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = urllib.error.URLError("fail")
        with pytest.raises(RuntimeError):
            http_get_json("https://example.com/api", retries=3)
        # Sleeps after attempt 0, 1, 2 (not after last failure at attempt 3)
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(0.4)
        mock_sleep.assert_any_call(0.8)
        mock_sleep.assert_any_call(pytest.approx(1.2))

    @mock.patch("data.http_utils.time.sleep")
    @mock.patch("data.http_utils.urllib.request.urlopen")
    def test_retries_on_json_decode_error(self, mock_urlopen, mock_sleep):
        bad_resp = self._mock_urlopen(b"not json")
        good_resp = self._mock_urlopen(json.dumps([1, 2]).encode())
        mock_urlopen.side_effect = [bad_resp, good_resp]
        result = http_get_json("https://example.com/api", retries=1)
        assert result == [1, 2]

    @mock.patch("data.http_utils.urllib.request.urlopen")
    def test_zero_retries(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("fail")
        with pytest.raises(RuntimeError, match="request failed"):
            http_get_json("https://example.com/api", retries=0)
        assert mock_urlopen.call_count == 1


# ---------------------------------------------------------------------------
# parse_float
# ---------------------------------------------------------------------------


class TestParseFloat:
    def test_none_returns_none(self):
        assert parse_float(None) is None

    def test_nan_returns_none(self):
        assert parse_float(float("nan")) is None

    def test_inf_returns_none(self):
        assert parse_float(float("inf")) is None
        assert parse_float(float("-inf")) is None

    def test_valid_int(self):
        assert parse_float(42) == 42.0

    def test_valid_float(self):
        assert parse_float(3.14) == pytest.approx(3.14)

    def test_valid_string_number(self):
        assert parse_float("0.75") == pytest.approx(0.75)

    def test_string_nan_returns_none(self):
        assert parse_float("nan") is None

    def test_string_inf_returns_none(self):
        assert parse_float("inf") is None
        assert parse_float("-inf") is None

    def test_invalid_string_returns_none(self):
        assert parse_float("not_a_number") is None

    def test_zero(self):
        assert parse_float(0) == 0.0

    def test_negative(self):
        assert parse_float(-1.5) == pytest.approx(-1.5)

    def test_empty_string_returns_none(self):
        assert parse_float("") is None

    def test_dict_returns_none(self):
        assert parse_float({}) is None


# ---------------------------------------------------------------------------
# parse_close_ts
# ---------------------------------------------------------------------------


class TestParseCloseTs:
    def test_none_returns_none(self):
        assert parse_close_ts(None) is None

    def test_empty_string_returns_none(self):
        assert parse_close_ts("") is None
        assert parse_close_ts("   ") is None

    def test_iso_with_z_suffix(self):
        ts = parse_close_ts("2024-01-15T12:30:00Z")
        assert ts is not None
        assert isinstance(ts, int)
        # 2024-01-15T12:30:00Z
        assert ts == 1705321800

    def test_iso_with_microseconds_z(self):
        ts = parse_close_ts("2024-06-01T00:00:00.000Z")
        assert ts is not None
        assert ts == 1717200000

    def test_date_only(self):
        ts = parse_close_ts("2024-01-01")
        assert ts is not None
        # 2024-01-01 00:00:00 UTC
        assert ts == 1704067200

    def test_datetime_with_offset(self):
        ts = parse_close_ts("2024-01-15 12:30:00+0000")
        assert ts is not None
        assert ts == 1705321800

    def test_plus_zero_zero_suffix_normalized(self):
        # Tests the "+00" -> "+00:00" normalization in the fallback
        ts = parse_close_ts("2024-01-15T12:30:00+00")
        assert ts is not None
        assert ts == 1705321800

    def test_iso_with_timezone_offset(self):
        ts = parse_close_ts("2024-01-15T12:30:00+00:00")
        assert ts is not None
        assert ts == 1705321800

    def test_invalid_returns_none(self):
        assert parse_close_ts("not-a-date") is None

    def test_zero_returns_none(self):
        assert parse_close_ts(0) is None

    def test_false_returns_none(self):
        assert parse_close_ts(False) is None


# ---------------------------------------------------------------------------
# parse_json_array
# ---------------------------------------------------------------------------


class TestParseJsonArray:
    def test_list_passthrough(self):
        assert parse_json_array([1, 2, 3]) == [1, 2, 3]

    def test_empty_list(self):
        assert parse_json_array([]) == []

    def test_json_string(self):
        assert parse_json_array('["a", "b"]') == ["a", "b"]

    def test_json_string_numbers(self):
        assert parse_json_array("[1, 2, 3]") == [1, 2, 3]

    def test_json_string_not_array(self):
        assert parse_json_array('{"key": "value"}') == []

    def test_invalid_json_string(self):
        assert parse_json_array("not json") == []

    def test_none_returns_empty(self):
        assert parse_json_array(None) == []

    def test_int_returns_empty(self):
        assert parse_json_array(42) == []

    def test_bool_returns_empty(self):
        assert parse_json_array(True) == []


# ---------------------------------------------------------------------------
# BaseDataProvider -- cache behaviour
# ---------------------------------------------------------------------------


class _ConcreteProvider(BaseDataProvider):
    """Minimal concrete subclass for testing."""

    name = "test_provider"

    def fetch(self, **kwargs: Any) -> Any:
        return {"fetched": True}


class TestBaseDataProviderCache:
    def test_get_cached_returns_none_when_empty(self):
        p = _ConcreteProvider()
        assert p.get_cached("missing") is None

    def test_set_then_get(self):
        p = _ConcreteProvider()
        p.set_cached("k", [1, 2, 3])
        assert p.get_cached("k") == [1, 2, 3]

    def test_cache_expires_after_ttl(self):
        p = _ConcreteProvider()
        p.set_cached("k", "value")
        # Manually backdate the timestamp so the entry is expired.
        p._cache_ts["k"] = time.time() - 400
        assert p.get_cached("k", ttl=300.0) is None
        # The expired entry should have been cleaned up.
        assert "k" not in p._cache
        assert "k" not in p._cache_ts

    def test_cache_valid_within_ttl(self):
        p = _ConcreteProvider()
        p.set_cached("k", "value")
        # Freshly set -- should be well within any reasonable TTL.
        assert p.get_cached("k", ttl=300.0) == "value"

    def test_custom_ttl(self):
        p = _ConcreteProvider()
        p.set_cached("k", 99)
        # Backdate by 5 seconds.
        p._cache_ts["k"] = time.time() - 5
        # Still valid with a 10-second TTL.
        assert p.get_cached("k", ttl=10.0) == 99
        # Expired with a 2-second TTL.
        assert p.get_cached("k", ttl=2.0) is None

    def test_logger_name(self):
        p = _ConcreteProvider()
        assert p.logger.name == "data.test_provider"

    def test_fetch_is_abstract(self):
        with pytest.raises(TypeError):
            BaseDataProvider()  # type: ignore[abstract]

    def test_concrete_fetch(self):
        p = _ConcreteProvider()
        assert p.fetch() == {"fetched": True}

    def test_overwrite_cached_value(self):
        p = _ConcreteProvider()
        p.set_cached("k", "old")
        p.set_cached("k", "new")
        assert p.get_cached("k") == "new"
