"""Optional hosted TradingView chart. Vendor data never enters research calculations."""

import html
import json
import re
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

INTERVALS = {"Daily": "D", "Weekly": "W", "Monthly": "M", "15 minutes": "15", "1 hour": "60"}


def validate_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not re.fullmatch(r"(?:NSE|BSE):[A-Z0-9][A-Z0-9&._-]{0,34}", symbol):
        raise ValueError(
            "Enter an Indian listing as EXCHANGE:SYMBOL, for example NSE:INFY or BSE:INFY."
        )
    return symbol


def suggested_symbol(dataset: dict) -> str:
    if dataset.get("is_synthetic"):
        return ""
    symbol = dataset["symbol"]
    if ":" not in symbol:
        if not dataset.get("history_quality"):
            return ""
        symbol = "NSE:" + symbol
    try:
        return validate_symbol(symbol)
    except ValueError:
        return ""


def chart_url(symbol: str) -> str:
    return "https://www.tradingview.com/chart/?symbol=" + quote(validate_symbol(symbol), safe="")


def widget_html(symbol: str, interval: str = "D", theme: str = "light") -> str:
    symbol = validate_symbol(symbol)
    if interval not in INTERVALS.values() or theme not in {"light", "dark"}:
        raise ValueError("Unsupported chart interval or theme.")
    options = {
        "autosize": True,
        "symbol": symbol,
        "interval": interval,
        "timezone": "Asia/Kolkata",
        "theme": theme,
        "style": "1",
        "locale": "en",
        "allow_symbol_change": False,
        "hide_side_toolbar": False,
        "calendar": False,
        "support_host": "https://www.tradingview.com",
    }
    # Official hosted-widget snippet, isolated in a Streamlit component iframe.
    # No credentials, local candles, evidence or backtest records are included.
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>html,body{{margin:0;height:100%;font-family:Arial,sans-serif}}
    .tradingview-widget-container{{height:100%;width:100%}}
    .tradingview-widget-container__widget{{height:calc(100% - 32px);width:100%}}
    .tradingview-widget-copyright{{font-size:12px;text-align:center;padding-top:8px}}
    a{{color:#607065}}</style></head><body>
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <div class="tradingview-widget-copyright"><a href="{html.escape(chart_url(symbol), quote=True)}"
        target="_blank" rel="noopener noreferrer">{html.escape(symbol)} chart by TradingView</a></div>
      <script src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
        type="text/javascript" async>{json.dumps(options)}</script>
    </div></body></html>"""


def tradingview_chart(dataset: dict) -> None:
    st.subheader("TradingView market chart")
    st.caption("EXTERNAL MARKET VIEW / DATA PROVIDED BY TRADINGVIEW")
    st.info(
        "This chart uses TradingView's available market data. Your historical research window, "
        "backtests and Monte Carlo continue to use the project's supplied prices."
    )
    if st.session_state.get("tv_research_stock") != dataset["symbol"]:
        st.session_state.tv_research_stock = dataset["symbol"]
        st.session_state.tv_symbol = suggested_symbol(dataset)
        st.session_state.pop("tv_chart", None)
    request = st.session_state.get("tv_chart", {})
    st.session_state.setdefault("tv_symbol", request.get("symbol", suggested_symbol(dataset)))
    with st.form("tradingview_chart_form"):
        st.text_input("TradingView symbol", key="tv_symbol", placeholder="NSE:INFY or BSE:INFY")
        a, b = st.columns(2)
        interval = a.selectbox("Initial chart interval", list(INTERVALS))
        theme = b.selectbox("Chart appearance", ["Light", "Dark"])
        load = st.form_submit_button("Load TradingView chart", type="primary")
    if load:
        try:
            request = {
                "symbol": validate_symbol(st.session_state.tv_symbol),
                "interval": INTERVALS[interval],
                "theme": theme.lower(),
            }
            st.session_state.tv_chart = request
        except ValueError as exc:
            st.error(str(exc))
            return
    st.caption(
        "Indian widget coverage is limited: BSE is listed as end-of-day; NSE may be unavailable. "
        "If a listing fails, verify the company's BSE ticker or open TradingView directly. "
        "Historical ticker names may have changed."
    )
    if not request:
        st.caption(
            "Choose a listing and load the chart. No TradingView login, API key or paid plan is required."
        )
        return
    st.markdown(f"**External chart: {request['symbol']}** · Research stock: {dataset['symbol']}")
    components.html(widget_html(**request), height=660, scrolling=False)
    st.link_button("Open this chart on TradingView", chart_url(request["symbol"]), width="stretch")
    st.caption(
        "If the embedded chart stays blank or says the symbol is unavailable, use the link above. "
        "Internet access is required; any exchange delay or market status is supplied by TradingView."
    )
    with st.expander("Chart source & availability"):
        st.markdown(
            "[Widget data coverage](https://www.tradingview.com/widget-docs/markets/asia-pacific/) · "
            "[TradingView data FAQ](https://www.tradingview.com/widget-docs/faq/data/)"
        )
        st.caption(
            "A TradingView subscription does not upgrade embedded-widget data. "
            "This embed displays the vendor's chart; it does not import prices, signals or indicators into the engine."
        )
