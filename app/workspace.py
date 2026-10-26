"""Small local workspace features, separate from market data and worker settings."""

from __future__ import annotations

import sqlite3
from datetime import date

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


def saved_research_period(symbol: str, bounds: tuple) -> tuple:
    saved = safe_storage(storage.get_setting, "research_period_" + symbol, default=[])
    try:
        start, end = (date.fromisoformat(value) for value in saved)
        if bounds[0] <= start < end <= bounds[1]:
            return start, end
    except (TypeError, ValueError):
        pass
    return bounds


def remember_research_period(symbol: str) -> None:
    period = st.session_state.get("period_" + symbol, ())
    if len(period) == 2:
        safe_storage(
            storage.set_setting, "research_period_" + symbol, [d.isoformat() for d in period]
        )


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
    from app.backtest_view import saved_experiments

    from app.quant_workspace import saved_quant_studies
    from app.experiment_ui import saved_validation_studies

    evidence = safe_storage(storage.list_evidence, limit=100, default=[]) or []
    reports = safe_storage(storage.list_reports, limit=100, default=[]) or []
    experiments_tab, studies_tab, cards_tab, reports_tab, watchlist_tab = st.tabs(
        ["Experiments", "Studies", "Evidence cards", "Analyst reports", "Research watchlist"]
    )
    with experiments_tab:
        saved_experiments()
    with studies_tab:
        kind = st.radio("Study type", ["Stock comparison", "Validation"], horizontal=True)
        if kind == "Stock comparison":
            saved_quant_studies()
        else:
            saved_validation_studies()
    symbols = sorted(
        {card.get("symbol", "Unknown") for card in evidence}
        | {report.get("evidence", {}).get("symbol", "Unknown") for report in reports}
    )
    with cards_tab:
        symbol = st.selectbox(
            "Filter saved instrument", ["All instruments", *symbols], key="saved_evidence_filter"
        )
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
            st.info("Build an evidence card in the stock desk Evidence tab.")
    with reports_tab:
        symbol = st.selectbox(
            "Filter saved instrument", ["All instruments", *symbols], key="saved_report_filter"
        )
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
            st.info("Generate a report in the stock desk Evidence tab.")
    with watchlist_tab:
        watchlist_editor()


def go_page(page: str) -> None:
    st.session_state.workspace_page = page


def select_demo(symbol: str) -> None:
    st.session_state.data_source = "Synthetic demo"
    st.session_state.demo_symbol = symbol


def select_history(symbol: str) -> None:
    st.session_state.data_source = "Historical library"
    st.session_state.historical_stock = symbol


def sidebar_navigation() -> None:
    st.sidebar.title("Equity")
    st.sidebar.caption("THE RESEARCH LEDGER")
    st.sidebar.button(
        "Stock desk",
        icon=":material/candlestick_chart:",
        width="stretch",
        type="primary"
        if st.session_state.get("workspace_page", "Stock workspace") == "Stock workspace"
        else "tertiary",
        on_click=go_page,
        args=("Stock workspace",),
    )
    groups = {
        "RESEARCH": {
            "Stock ideas": "analytics",
            "Quant research": "science",
            "Paper journal": "receipt_long",
            "Saved research": "history",
        },
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


def go_stock_section(section: str) -> None:
    st.session_state.workspace_page = "Stock workspace"
    st.session_state.stock_section = section


def sidebar_workspace(dataset: dict | None) -> None:
    if dataset and st.sidebar.button(
        "Save instrument to watchlist", icon=":material/bookmark_add:", width="stretch"
    ):
        source = (
            "Synthetic demo"
            if dataset["is_synthetic"]
            else "Historical library"
            if dataset.get("history_quality")
            else "Historical CSV"
        )
        if safe_storage(save_watchlist_item, dataset["symbol"], source):
            st.toast("Instrument saved to your research watchlist.", icon=":material/bookmark:")
    entries = safe_storage(storage.get_setting, "research_watchlist", default=[]) or []
    with st.sidebar.expander(f"Research watchlist · {len(entries)}", expanded=False):
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
            elif item["source"] == "Historical library":
                st.button(
                    item["symbol"],
                    key=f"watch_{item['id']}",
                    type="tertiary",
                    icon=":material/bookmark:",
                    on_click=select_history,
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
