from __future__ import annotations

from unittest import mock

import pytest

from data.aviationweather import AviationWeatherProvider


def _metar_payload(temp_c: float = 2.0):
    return [
        {
            "icaoId": "KORD",
            "temp": temp_c,
            "rawOb": "KORD TEST",
        }
    ]


def _taf_payload():
    return [
        {
            "icaoId": "KORD",
            "fcsts": [
                {
                    "timeFrom": 1773252000,
                    "timeTo": 1773259200,
                    "fcstChange": None,
                    "wxString": "-RA",
                    "probability": None,
                    "visib": 4,
                },
                {
                    "timeFrom": 1773255600,
                    "timeTo": 1773259200,
                    "fcstChange": "TEMPO",
                    "wxString": "-SN",
                    "probability": None,
                    "visib": 2,
                },
            ],
        }
    ]


class TestAviationWeatherProvider:
    def setup_method(self) -> None:
        self.provider = AviationWeatherProvider()

    @mock.patch("data.aviationweather.http_get_json")
    def test_get_metar(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = _metar_payload(5.0)
        metar = self.provider.get_metar("KORD")
        assert metar is not None
        assert metar["icaoId"] == "KORD"

    @mock.patch("data.aviationweather.http_get_json")
    def test_latest_temperature_f(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = _metar_payload(10.0)
        temp_f = self.provider.latest_temperature_f("KORD")
        assert temp_f == pytest.approx(50.0)

    @mock.patch("data.aviationweather.http_get_json")
    def test_get_taf(self, mock_http: mock.MagicMock) -> None:
        mock_http.return_value = _taf_payload()
        taf = self.provider.get_taf("KORD")
        assert taf is not None
        assert len(taf["fcsts"]) == 2

    @mock.patch("data.aviationweather.http_get_json")
    def test_taf_precip_probability_from_explicit_segments(self, mock_http: mock.MagicMock, monkeypatch) -> None:
        mock_http.return_value = _taf_payload()
        # Fix "now" so the first segment overlaps the computed window.
        class _Frozen:
            @classmethod
            def now(cls, tz=None):
                import datetime as _dt

                return _dt.datetime.fromtimestamp(1773252000, tz=tz or _dt.timezone.utc)

        monkeypatch.setattr("data.aviationweather.datetime", _Frozen)
        prob = self.provider.taf_precip_probability("KORD", hours=3, precip_kind="rain")
        assert prob is not None
        assert 0.5 <= prob <= 0.9
