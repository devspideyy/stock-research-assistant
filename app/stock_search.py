"""Search identifiers without implying that every listing has research prices."""

import json

import streamlit as st

from app import history, instruments
from app.computation import file_version
from app.workspace import select_history


@st.cache_data(max_entries=2, show_spinner=False)
def _catalogue(version: tuple) -> list[dict]:
    return json.loads(instruments.CACHE.read_text(encoding="utf-8"))["instruments"]


def stock_records() -> list[dict]:
    ready = set(history.ready_stocks())
    rows = _catalogue(file_version(instruments.CACHE)) if instruments.CACHE.exists() else []
    records = {
        f"{r['exchange']}:{r['trading_symbol']}": {
            **r,
            "history_ready": r["exchange"] == "NSE" and r["trading_symbol"] in ready,
        }
        for r in rows
    }
    for symbol in ready:
        records.setdefault(
            "NSE:" + symbol,
            {
                "exchange": "NSE",
                "trading_symbol": symbol,
                "name": symbol,
                "isin": "",
                "history_ready": True,
            },
        )
    return sorted(
        records.values(), key=lambda r: (not r["history_ready"], r["trading_symbol"], r["exchange"])
    )


def open_stock(symbol: str) -> None:
    select_history(symbol)
    st.session_state.workspace_page = "Stock workspace"
    st.session_state.stock_section = "Chart & indicators"
    st.session_state.chart_workspace = "Research chart"


def stock_search() -> None:
    with st.expander("Find a stock · company, symbol or ISIN"):
        query = (
            st.text_input("Find stock", placeholder="Infosys, RELIANCE, INE…").strip().casefold()
        )
        records = stock_records()
        if not instruments.CACHE.exists():
            st.caption(
                "Prepared histories are searchable now. Refresh Stock universe for the full public NSE/BSE identifier catalogue."
            )
        matches = [
            r
            for r in records
            if not query or query in f"{r['name']} {r['trading_symbol']} {r['isin']}".casefold()
        ]
        st.caption(f"{len(matches):,} matching listings · refine your search · up to 50 shown")
        if not matches:
            st.info("No matching listing in the local catalogue.")
            return
        selected = st.selectbox(
            "Research stock search result",
            matches[:50],
            format_func=lambda r: (
                f"{r['exchange']}:{r['trading_symbol']} · {r['name']} · {'History ready' if r['history_ready'] else 'Identifier only'}"
            ),
        )
        if selected["history_ready"]:
            st.button(
                "Open research chart",
                on_click=open_stock,
                args=(selected["trading_symbol"],),
                type="primary",
            )
        elif selected["exchange"] == "NSE":
            listing = history.catalogue()
            available = any(
                r["symbol"] == selected["trading_symbol"] for r in listing.get("stocks", [])
            )
            st.info(
                "This listing has no prepared prices. Historical coverage is checked before a chart can open."
            )
            if st.button("Prepare available pre-2021 history", disabled=not available):
                try:
                    with st.spinner(
                        "Downloading the pinned historical source and checking coverage…"
                    ):
                        history.fetch_stock(selected["trading_symbol"])
                    st.session_state.pending_research_stock = selected["trading_symbol"]
                    st.rerun()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.error(str(exc))
        else:
            st.info(
                "BSE identifier only. Research history currently uses prepared NSE listings; use the company's NSE listing when available."
            )
