from __future__ import annotations

from unittest import mock

from data.nws_climate import NWSClimateProvider


CLI_SAMPLE = """
000
CDUS41 KOKX 110636
CLILGA

...THE LAGUARDIA NY CLIMATE SUMMARY FOR MARCH 10 2026...

TEMPERATURE (F)
 YESTERDAY
  MAXIMUM         78R   107 PM  78    2016  48     30       67
  MINIMUM         45    308 AM  12    1984  35     10       46

PRECIPITATION (IN)
  YESTERDAY        0.00          1.52 1994   0.13  -0.13     0.00
  MONTH TO DATE    1.86                      1.27   0.59     1.54

SNOWFALL (IN)
  YESTERDAY        0.0           2.4  2017   0.2   -0.2      0.0
  MONTH TO DATE    T                         2.4   -2.4      0.0
"""


CF6_SAMPLE = """
000
CXUS53 KLOT 110800
CF6ORD
PRELIMINARY LOCAL CLIMATOLOGICAL DATA (WS FORM: F-6)
                                          STATION:   CHICAGO-OHARE
                                          MONTH:     MARCH
                                          YEAR:      2026

DY MAX MIN AVG DEP HDD CDD  WTR  SNW DPTH SPD SPD DIR MIN PSBL S-S WX    SPD DR
================================================================================
 1  32  24  28  -6  37   0 0.00  0.0    0 12.7 21  30   M    M   6        27  80
 2  43  24  34   0  31   0 0.00  0.0    0  7.3 15 120   M    M   3        19 110
 3  42  33  38   4  27   0 0.01  0.0    0  6.3 14  30   M    M  10 18     18  30
 4  46  32  39   4  26   0 0.13  0.0    0  8.3 13  40   M    M  10 128    23  10
10  62  38  50  13  15   0 1.02    T    0 12.2 23 320   M    M   9 135    33  10
================================================================================
TOTAL FOR MONTH:   2.13
TOTAL MONTH:  T
[NO. OF DAYS WITH]
0.01 INCH OR MORE:   3
"""


def test_parse_cli_extracts_daily_climate_fields():
    provider = NWSClimateProvider()
    parsed = provider.parse_cli(CLI_SAMPLE)
    assert parsed is not None
    assert parsed["report_date"] == "2026-03-10"
    assert parsed["max_temp_f"] == 78.0
    assert parsed["min_temp_f"] == 45.0
    assert parsed["month_to_date_precip_in"] == 1.86
    assert parsed["month_to_date_snow_in"] == 0.001


def test_parse_cf6_extracts_rows_and_precip_days():
    provider = NWSClimateProvider()
    parsed = provider.parse_cf6(CF6_SAMPLE)
    assert parsed is not None
    assert parsed["year"] == 2026
    assert parsed["month"] == 3
    assert len(parsed["rows"]) == 5
    assert parsed["rows"][-1]["precip_in"] == 1.02
    assert parsed["precip_days"] == 3
    assert parsed["month_to_date_precip_in"] == 2.13
    assert parsed["month_to_date_snow_in"] == 0.001


@mock.patch.object(NWSClimateProvider, "get_cf6")
def test_month_to_date_summary_uses_cf6_product(mock_get_cf6: mock.MagicMock):
    mock_get_cf6.return_value = {"productText": CF6_SAMPLE}
    provider = NWSClimateProvider()
    summary = provider.get_month_to_date_summary("ORD", target_year=2026, target_month=3)
    assert summary is not None
    assert summary["location_id"] == "ORD"
    assert summary["precip_in"] == 2.13
    assert summary["precip_days"] == 3
    assert summary["last_reported_day"] == 10
