"""Vendor chart input isolation and stock-switch behavior; no network needed."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.tradingview import suggested_symbol, validate_symbol, widget_html

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(item for item in app.button if item.label == label)


@pytest.mark.parametrize(
    "value", ["NSE:INFY</script>", "https://example.com", "NYSE:INFY", 'NSE:INFY"', "NSE:"]
)
def test_embed_rejects_html_urls_and_out_of_scope_exchanges(value):
    with pytest.raises(ValueError):
        widget_html(value)


def test_embed_uses_fixed_vendor_and_never_contains_local_research_prices():
    assert validate_symbol(" bse:infy ") == "BSE:INFY"
    source = widget_html("NSE:M&M", interval="W", theme="dark")
    assert '"symbol": "NSE:M&M"' in source
    assert "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" in source
    assert '"allow_symbol_change": false' in source
    assert "candles" not in source and "UPSTOX" not in source
    assert suggested_symbol({"symbol": "DEMO_ENERGY", "is_synthetic": True}) == ""
    assert (
        suggested_symbol(
            {"symbol": "INFY", "is_synthetic": False, "history_quality": {"source": "pinned"}}
        )
        == "NSE:INFY"
    )
    assert suggested_symbol({"symbol": "MY_NSE_STOCK", "is_synthetic": False}) == ""


def test_chart_load_is_explicit_and_stock_changes_clear_external_symbol():
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    button(app, "Charts & indicators").click().run()
    assert not app.get("iframe")
    next(item for item in app.radio if item.label == "Chart workspace").set_value(
        "TradingView"
    ).run()
    assert not app.exception
    assert not app.get("iframe")
    next(item for item in app.text_input if item.label == "TradingView symbol").set_value(
        "BSE:INFY"
    )
    button(app, "Load TradingView chart").click().run()
    assert not app.exception
    assert app.session_state["tv_chart"]["symbol"] == "BSE:INFY"
    assert app.get("iframe")
    assert "backtests" not in app.session_state
    assert "analysis" not in app.session_state
    next(item for item in app.selectbox if item.label == "Demonstration instrument").set_value(
        "DEMO_TECH"
    ).run()
    assert not app.exception
    assert "tv_chart" not in app.session_state
    assert not app.get("iframe")
