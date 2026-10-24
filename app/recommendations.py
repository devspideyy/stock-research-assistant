"""Research recommendations with visible rules, sources and eligibility boundaries."""

from datetime import time
import hashlib

import pandas as pd
import streamlit as st

from app import storage
from app.assessment import STRATEGIES, STRATEGY_GUIDE
from app.accounting import market_options
from app.demo import SYMBOLS, load_demo
from app.engine_bridge import EngineClient, load_candles_csv, validate_daily_candles
from app.services import build_evidence
from app.ui_helpers import json_download, render_assessment
from app.workspace import safe_storage


def strategy_guide() -> None:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Strategy": label,
                    "Context": STRATEGY_GUIDE[key][0],
                    "Entry hypothesis": STRATEGY_GUIDE[key][1],
                    "Exit / main risk": STRATEGY_GUIDE[key][2],
                }
                for label, key in STRATEGIES.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Predefined educational hypotheses—not universally recommended strategies. Test the same evaluation window, costs and capital; do not select winners using an already-inspected holdout."
    )


def stock_ideas(dataset: dict | None) -> None:
    st.write(
        "Compare available stock histories, inspect opposing cases and shortlist research candidates."
    )
    st.caption(
        "Stock catalogue identifiers alone cannot be rated. This scanner requires price histories and makes no authenticated requests."
    )
    source = st.radio(
        "Idea source",
        [
            "Current research dataset",
            "Five fictional demo scenarios",
            "Multiple historical CSV files",
        ],
        horizontal=True,
    )
    uploaded, synthetic, completed, close_time = [], False, False, time(15, 30)
    if source == "Multiple historical CSV files":
        uploaded = st.file_uploader(
            "Stock histories (up to 10 CSV files)", type=["csv"], accept_multiple_files=True
        )
        synthetic = st.checkbox("These uploaded histories are fictional / test data")
        completed = st.checkbox("I confirm the uploaded histories contain completed daily bars")
        close_time = st.time_input("Batch decision time (India time)", value=close_time)
        st.caption(
            "Each file uses Date/Timestamp, Open, High, Low, Close, Volume. File names identify instruments. Confirm actual close times and consistent corporate-action adjustments against the source."
        )
    if source == "Five fictional demo scenarios":
        st.warning(
            "Fictional instruments only. This ranking is a software demonstration, not a real-stock shortlist."
        )
    fingerprint = (
        source,
        st.session_state.get("dataset_fingerprint")
        if source == "Current research dataset" and dataset is not None
        else None,
        tuple((file.name, hashlib.sha256(file.getvalue()).hexdigest()) for file in uploaded),
        synthetic,
        completed,
        str(close_time),
    )
    if st.session_state.get("idea_input") != fingerprint:
        st.session_state.pop("idea_cards", None)
        st.session_state.idea_input = fingerprint
    if st.button("Assess available stocks", type="primary"):
        try:
            if source == "Current research dataset":
                if dataset is None:
                    raise ValueError(
                        "Select a demo or upload a historical dataset in the sidebar first."
                    )
                datasets = [dataset]
            elif source == "Five fictional demo scenarios":
                datasets = [load_demo(symbol) | {"bar_interval": "1d"} for symbol in SYMBOLS]
            else:
                if not uploaded or len(uploaded) > 10 or not completed:
                    raise ValueError("Provide 1–10 CSV files and confirm completed daily bars.")
                datasets = [
                    {
                        "symbol": file.name.rsplit(".", 1)[0],
                        "candles": load_candles_csv(file.getvalue()),
                        "is_synthetic": synthetic,
                        "bar_interval": "1d",
                    }
                    for file in uploaded
                ]
            cards = []
            with st.spinner("Calculating native price structure and evidence cases…"):
                for item in datasets:
                    candles = validate_daily_candles(
                        item["candles"], item.get("bar_interval", "unconfirmed")
                    )
                    cutoff = item.get("decision_time")
                    if not cutoff and len(candles[-1]["timestamp"]) == 10:
                        cutoff = candles[-1]["timestamp"] + "T" + close_time.isoformat() + "+05:30"
                    card = build_evidence(
                        candles,
                        EngineClient().analyze(candles, **market_options(item)),
                        symbol=item["symbol"],
                        news=item.get("news"),
                        fundamentals=item.get("fundamentals"),
                        is_synthetic=item["is_synthetic"],
                        decision_time=cutoff,
                    )
                    cards.append(card)
            st.session_state.idea_cards = cards
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    cards = st.session_state.get("idea_cards", [])
    if cards:
        st.caption(
            "Last completed scan · sort by evidence gap, not expected return · input scope is preserved per row"
        )
        rows = []
        for card in cards:
            case = card["assessment"]
            rows.append(
                {
                    "Symbol": card["symbol"],
                    "As of": card["as_of"],
                    "Scope": case["scope"],
                    "Stance": case["stance"],
                    "Bullish": case["bullish"],
                    "Bearish": case["bearish"],
                    "Evidence gap": case["bullish"] - case["bearish"]
                    if case["bullish"] is not None
                    else None,
                    "Regime": case["regime"],
                    "Research gate": card["action"],
                }
            )
        st.dataframe(
            pd.DataFrame(rows).sort_values("Evidence gap", ascending=False, na_position="last"),
            hide_index=True,
            width="stretch",
        )
        selected = st.selectbox(
            "Inspect stock research case",
            range(len(cards)),
            format_func=lambda i: f"{cards[i]['symbol']} · {cards[i]['as_of']}",
        )
        render_assessment(cards[selected])
        if st.button("Save selected stock research case", icon=":material/bookmark_add:"):
            if safe_storage(storage.save_evidence, cards[selected]):
                st.success("Evidence and its rating saved to Saved research.")
        st.download_button(
            "Export stock research cases",
            json_download(cards),
            "stock_research_cases.json",
            mime="application/json",
        )
    with st.expander("Strategy library and assumptions"):
        strategy_guide()
