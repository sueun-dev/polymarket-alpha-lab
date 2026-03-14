from data.global_climate import GlobalClimateProvider


NASA_SAMPLE = """
        GLOBAL Land-Ocean Temperature Index in 0.01 degrees Celsius   base period: 1951-1980
Year   Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec    J-D D-N    DJF  MAM  JJA  SON  Year
2022    92   95   98   94   90   89   93  101   97  104  102   98     96  96     95   94   94  101  2022
2023   101  110  112  109  103  101  107  114  111  116  115  112    110 110    103  108  107  114  2023
2024   125  143  139  131  116  124  120  130  123  134  129  126    128 129    134  129  125  129  2024
2025   137  126  137  124  108  106  102  117  125  119  121  107    119 121    130  123  108  121  2025
2026   108  124 **** **** **** **** **** **** **** **** **** ****   **** ***    113 **** **** ****  2026
"""

BERKELEY_FEB_2025_HTML = """
<html><body>
<p>The following is a summary of global temperature conditions in Berkeley Earth’s analysis of February 2025.</p>
<p>Globally, February 2025 was the third warmest February since directly measured instrumental records began in 1850, behind 2024 and 2016. February 2025 was measured as 1.49 ± 0.12 °C (2.69 ± 0.21 °F) above the corresponding 1850-1900 average.</p>
</body></html>
"""

BERKELEY_JAN_2025_HTML = """
<html><body>
<p>The following is a summary of global temperature conditions in Berkeley Earth’s analysis of January 2025.</p>
<p>Globally, January 2025 was the warmest January since directly measured instrumental records began in 1850. January 2025 was measured as 1.64 ± 0.11 °C (2.95 ± 0.19 °F) above the corresponding 1850-1900 average.</p>
</body></html>
"""


def test_parse_nasa_monthly_series_extracts_latest_month():
    provider = GlobalClimateProvider()
    parsed = provider.parse_nasa_monthly_series(NASA_SAMPLE)
    assert parsed["latest_year"] == 2026
    assert parsed["latest_month"] == 2
    august_2024 = next(row for row in parsed["rows"] if row["year"] == 2024 and row["month"] == 8)
    assert august_2024["anomaly_c"] == 1.30


def test_estimate_monthly_anomaly_returns_published_actual():
    provider = GlobalClimateProvider()
    provider.get_monthly_series = lambda: provider.parse_nasa_monthly_series(NASA_SAMPLE)
    provider.get_berkeley_monthly_update = lambda *args, **kwargs: None
    estimate = provider.estimate_monthly_anomaly(2026, 2)
    assert estimate is not None
    assert estimate["is_published"] is True
    assert estimate["actual_c"] == 1.24
    assert estimate["mu_c"] == 1.24


def test_estimate_monthly_anomaly_nowcasts_future_month():
    provider = GlobalClimateProvider()
    provider.get_monthly_series = lambda: provider.parse_nasa_monthly_series(NASA_SAMPLE)
    provider.get_berkeley_monthly_update = lambda *args, **kwargs: None
    estimate = provider.estimate_monthly_anomaly(2026, 3)
    assert estimate is not None
    assert estimate["is_published"] is False
    assert estimate["mu_c"] > 1.0
    assert estimate["sigma_c"] >= 0.04
    assert 0.28 <= estimate["confidence"] <= 0.76


def test_record_threshold_uses_prior_years_only():
    provider = GlobalClimateProvider()
    provider.get_monthly_series = lambda: provider.parse_nasa_monthly_series(NASA_SAMPLE)
    assert provider.record_threshold_c(2026, 8) == 1.30


def test_parse_berkeley_monthly_update_extracts_anomaly_and_rank():
    provider = GlobalClimateProvider()
    parsed = provider.parse_berkeley_monthly_update(BERKELEY_FEB_2025_HTML, year=2025, month=2)
    assert parsed is not None
    assert parsed["anomaly_c"] == 1.49
    assert parsed["uncertainty_c"] == 0.12
    assert parsed["rank"] == 3
    assert parsed["is_record"] is False


def test_parse_berkeley_monthly_update_recognizes_record_month():
    provider = GlobalClimateProvider()
    parsed = provider.parse_berkeley_monthly_update(BERKELEY_JAN_2025_HTML, year=2025, month=1)
    assert parsed is not None
    assert parsed["rank"] == 1
    assert parsed["is_record"] is True


def test_estimate_monthly_anomaly_blends_nasa_and_berkeley_actuals():
    provider = GlobalClimateProvider()
    provider.get_monthly_series = lambda: provider.parse_nasa_monthly_series(NASA_SAMPLE)
    provider.get_berkeley_monthly_update = lambda year, month: (
        provider.parse_berkeley_monthly_update(BERKELEY_FEB_2025_HTML, year=2025, month=2)
        if (year, month) == (2025, 2)
        else None
    )
    estimate = provider.estimate_monthly_anomaly(2025, 2)
    assert estimate is not None
    assert estimate["is_published"] is True
    assert estimate["source_count"] == 2
    assert estimate["nasa_actual_c"] == 1.26
    assert estimate["berkeley_actual_c"] == 1.49
    assert estimate["actual_c"] == 1.375
    assert estimate["release_state"] == "published_dual_source"


def test_estimate_monthly_anomaly_marks_nowcast_release_state():
    provider = GlobalClimateProvider()
    provider.get_monthly_series = lambda: provider.parse_nasa_monthly_series(NASA_SAMPLE)
    provider.get_berkeley_monthly_update = lambda *args, **kwargs: None
    estimate = provider.estimate_monthly_anomaly(2026, 3)
    assert estimate is not None
    assert estimate["is_published"] is False
    assert estimate["release_state"] == "nowcast_nasa_anchor"
    assert estimate["nasa_published"] is False
    assert estimate["berkeley_published"] is False
