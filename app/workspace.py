"""Small local workspace features, separate from market data and worker settings."""

from __future__ import annotations

import sqlite3
import os

import pandas as pd
import streamlit as st

from app import storage
from app.demo import SYMBOLS
from app.ui_helpers import json_download, render_evidence, render_report


def safe_storage(callable_, *args, default=None, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except (RuntimeError, OSError, sqlite3.Error) as exc:
        st.warning(f"Local storage is unavailable: {exc}")
        return default


def save_watchlist_item(symbol: str, source: str, instrument_key: str = "") -> bool:
    """Save identifiers only; this list never changes the monitoring worker's list."""
    entries = storage.get_setting("research_watchlist", [])
    identity = instrument_key or f"{source}:{symbol}"
    entries = [item for item in entries if item["id"] != identity]
    entries.append(
        {"id": identity, "symbol": symbol, "source": source, "instrument_key": instrument_key}
    )
    storage.set_setting("research_watchlist", entries[-50:])
    return True


def remove_watchlist_item(identity: str) -> bool:
    entries = storage.get_setting("research_watchlist", [])
    storage.set_setting("research_watchlist", [item for item in entries if item["id"] != identity])
    return True


def watchlist_editor() -> None:
    entries = safe_storage(storage.get_setting, "research_watchlist", default=[]) or []
    st.caption("Research watchlist · saved locally · up to 50 entries")
    if not entries:
        st.info("Save a demo/import from the sidebar or a real identifier from Stock universe.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Instrument": item["symbol"],
                    "Source": item["source"],
                    "Provider key": item["instrument_key"],
                }
                for item in entries
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    selected = st.selectbox(
        "Saved watchlist item",
        entries,
        format_func=lambda row: f"{row['symbol']} · {row['source']}",
    )
    if st.button("Remove from research watchlist", icon=":material/bookmark_remove:"):
        if safe_storage(remove_watchlist_item, selected["id"]):
            st.rerun()
    st.caption(
        "Identifiers are not connected prices. Monitoring has its own explicitly configured watchlist."
    )


def saved_research() -> None:
    """Browse saved records without replacing the currently selected research data."""
    evidence = safe_storage(storage.list_evidence, limit=100, default=[]) or []
    reports = safe_storage(storage.list_reports, limit=100, default=[]) or []
    first, second = st.columns(2)
    first.metric("Recent evidence cards", len(evidence), border=True)
    second.metric("Recent analyst reports", len(reports), border=True)
    st.caption(
        "Most recent 100 records of each kind. Snapshots retain their original data labels and timestamps."
    )
    symbols = sorted(
        {card.get("symbol", "Unknown") for card in evidence}
        | {report.get("evidence", {}).get("symbol", "Unknown") for report in reports}
    )
    symbol = st.selectbox("Filter saved instrument", ["All instruments", *symbols])
    cards_tab, reports_tab, watchlist_tab = st.tabs(
        ["Evidence cards", "Analyst reports", "Research watchlist"]
    )
    with cards_tab:
        cards = [
            card for card in evidence if symbol == "All instruments" or card.get("symbol") == symbol
        ]
        if cards:
            selected = st.selectbox(
                "Saved evidence",
                cards,
                format_func=lambda card: f"{card['symbol']} · {card['as_of']} · {card['id']}",
            )
            st.badge(
                "Synthetic"
                if selected.get("data_quality", {}).get("synthetic")
                else "Imported / provenance in record",
                color="orange",
            )
            render_evidence(selected)
            st.download_button(
                "Export saved evidence",
                json_download(selected),
                "saved_evidence.json",
                mime="application/json",
            )
        else:
            st.info("Build an evidence card in Overview to start your research history.")
    with reports_tab:
        items = [
            report
            for report in reports
            if symbol == "All instruments" or report.get("evidence", {}).get("symbol") == symbol
        ]
        if items:
            selected = st.selectbox(
                "Saved analyst report",
                range(len(items)),
                format_func=lambda i: (
                    f"{items[i]['evidence']['symbol']} · {items[i]['generated_at']} · {items[i]['provider']}"
                ),
            )
            report = items[selected]
            st.caption(
                f"Data as of {report['evidence']['as_of']} · Saved report, not a new analysis"
            )
            render_report(report)
            st.download_button(
                "Export saved report",
                json_download(report),
                "saved_report.json",
                mime="application/json",
            )
        else:
            st.info("Generate an analyst report in Overview. Rules mode works without a key.")
    with watchlist_tab:
        watchlist_editor()


def go_page(page: str) -> None:
    st.session_state.workspace_page = page


def select_demo(symbol: str) -> None:
    st.session_state.data_source = "Synthetic demo"
    st.session_state.demo_symbol = symbol


def sidebar_navigation() -> None:
    st.sidebar.title("Equity")
    st.sidebar.caption("RESEARCH TERMINAL / INDIA")
    groups = {
        "RESEARCH": {
            "Overview": "space_dashboard",
            "Market analysis": "candlestick_chart",
            "Assistant": "forum",
            "Saved research": "history",
        },
        "EXPERIMENTS": {"Backtesting": "query_stats", "Monte Carlo": "ssid_chart"},
        "WORKSPACE": {
            "Stock universe": "travel_explore",
            "Monitoring": "sensors",
            "Settings": "tune",
        },
    }
    for group, pages in groups.items():
        st.sidebar.caption(group)
        for page, icon in pages.items():
            st.sidebar.button(
                page,
                key=f"nav_{page}",
                icon=f":material/{icon}:",
                type="primary"
                if st.session_state.get("workspace_page", "Overview") == page
                else "tertiary",
                width="stretch",
                on_click=go_page,
                args=(page,),
            )
    st.sidebar.divider()


def sidebar_workspace(dataset: dict | None) -> None:
    if dataset and st.sidebar.button(
        "Save instrument to watchlist", icon=":material/bookmark_add:", width="stretch"
    ):
        source = "Synthetic demo" if dataset["is_synthetic"] else "Historical CSV"
        if safe_storage(save_watchlist_item, dataset["symbol"], source):
            st.toast("Instrument saved to your research watchlist.", icon=":material/bookmark:")
    entries = safe_storage(storage.get_setting, "research_watchlist", default=[]) or []
    with st.sidebar.expander(f"Research watchlist · {len(entries)}", expanded=True):
        if not entries:
            st.caption("Save your current instrument or a stock from the catalogue.")
        for item in entries[-4:]:
            if item["source"] == "Synthetic demo" and item["symbol"] in SYMBOLS:
                st.button(
                    item["symbol"].replace("DEMO_", "").title(),
                    key=f"watch_{item['id']}",
                    type="tertiary",
                    icon=":material/bookmark:",
                    on_click=select_demo,
                    args=(item["symbol"],),
                )
            else:
                st.markdown(f"**{item['symbol']}**")
            st.caption(
                f"{item['source']} · {'Not live' if item['source'] == 'Synthetic demo' else 'Identifier / import only'}"
            )
        if entries:
            st.button(
                "Manage watchlist",
                key="manage_watchlist",
                on_click=go_page,
                args=("Saved research",),
            )
    st.sidebar.caption("CONNECTIONS")
    st.sidebar.caption(
        "Broker · Token configured, unverified"
        if os.getenv("UPSTOX_ACCESS_TOKEN")
        else "Broker · Not connected"
    )
    st.sidebar.caption(
        "OpenRouter · Key configured, unverified"
        if os.getenv("OPENROUTER_API_KEY")
        else "OpenRouter · Not configured"
    )
    st.sidebar.caption("Level 2/3 · Deferred")
