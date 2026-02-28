def test_dashboard_imports():
    from dashboard.pages.overview import render as r1
    from dashboard.pages.strategies import render as r2
    from dashboard.pages.markets import render as r3
    from dashboard.pages.backtest_page import render as r4
    assert callable(r1)
    assert callable(r2)
    assert callable(r3)
    assert callable(r4)
