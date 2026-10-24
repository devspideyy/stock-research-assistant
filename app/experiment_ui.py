"""Readable UI pieces for offline experiments; calculations stay in the C++ engine."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import storage
from app.accounting import SOURCES, VERIFIED_THROUGH, nse_delivery_schedule
from app.assessment import STRATEGIES
from app.ui_helpers import COLORS, chart_layout, json_download, number, percent, show_items
from app.validation import run_validation, save_study, summary_rows
from app.workspace import safe_storage


def cost_model_selector(key: str) -> str:
    return st.selectbox("Cost model", ["Hypothetical bps", "NSE delivery estimate"], key=key)


def cost_controls(model: str, key: str) -> dict:
    if model == "Hypothetical bps":
        commission = st.number_input(
            "Commission / charges per side (bps)",
            min_value=0.0,
            max_value=500.0,
            value=10.0,
            key=key + "_commission",
        )
        st.caption("Editable all-in research assumption; not an exchange or broker fee quote.")
        return {"commission_bps": commission}
    st.caption(
        f"NSE cash delivery only · reviewed coverage 1 Oct 2024 – {VERIFIED_THROUGH}. "
        "Other trade dates are rejected. Confirm exchange, product and broker terms against your source."
    )
    a, b, c = st.columns(3)
    brokerage = a.number_input("Brokerage per side (bps)", 0.0, 500.0, 0.0, key=key + "_brokerage")
    cap = b.number_input(
        "Brokerage cap per fill (₹; 0 = none)", 0.0, 10000.0, 0.0, key=key + "_cap"
    )
    dp = c.number_input("DP per sell (₹ before GST)", 0.0, 1000.0, 13.0, key=key + "_dp")
    st.caption(
        "DP defaults to an editable broker example. Estimates exclude invoice rounding and personal taxes."
    )
    return {
        "cost_schedule": nse_delivery_schedule(
            brokerage_bps=brokerage, brokerage_cap=cap, dp_sell=dp
        )
    }


def data_readiness(dataset: dict) -> None:
    """Concrete input metadata, not a green 'validated data' badge."""
    with st.expander("Data & accounting context"):
        a, b, c = st.columns(3)
        a.metric("Price basis", dataset.get("price_basis", "unverified").title(), border=True)
        b.metric("Declared actions", len(dataset.get("corporate_actions", [])), border=True)
        c.metric("Daily bars", len(dataset["candles"]), border=True)
        st.caption(
            f"{dataset['candles'][0]['timestamp']} → {dataset['candles'][-1]['timestamp']} · "
            "Source completeness and the exchange holiday calendar are not certified."
        )
        if dataset.get("corporate_actions"):
            st.dataframe(
                pd.DataFrame(dataset["corporate_actions"]), hide_index=True, width="stretch"
            )
            st.caption(
                "C++ signals account for these declared events. Chart candles retain raw source prices; "
                "TA-Lib's separate indicator library uses supplied OHLCV without event normalisation."
            )
        elif dataset.get("price_basis", "unverified") != "adjusted":
            st.caption(
                "No actions declared. Missing splits or dividends can distort signals and returns."
            )


def accounting_view(result: dict) -> None:
    metrics = result.get("metrics", {})
    a, b, c = st.columns(3)
    a.metric("Fees paid", number(metrics.get("fees_paid")), border=True)
    b.metric("Gross dividends earned", number(metrics.get("dividend_income")), border=True)
    c.metric("Dividend receivable", number(metrics.get("dividend_receivable")), border=True)
    left, right = st.columns(2)
    with left:
        st.markdown("**Charge components**")
        fees = result.get("fee_breakdown", {})
        if fees:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Component": k.replace("_", " ").title(), "Amount": v}
                        for k, v in fees.items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("No charges incurred.")
    with right:
        st.markdown("**Corporate-action ledger**")
        if result.get("action_ledger"):
            st.dataframe(pd.DataFrame(result["action_ledger"]), hide_index=True, width="stretch")
        else:
            st.caption(
                "No declared events in this evaluation window. Try Accounting example in Research data."
            )
    st.caption(
        "Unpaid gross dividend entitlements count in equity, but cannot fund purchases. "
        "Final holdings are marked to market; no final sell charges are invented."
    )


def validation_lab(dataset: dict) -> None:
    st.write("Challenge fixed rules across separate periods, then double costs and slippage.")
    data_readiness(dataset)
    if dataset["is_synthetic"]:
        st.caption(
            "Fictional-data exercise · checks software behaviour, not real-market performance."
        )
    model = cost_model_selector("validation_cost_model")
    with (
        st.expander("Study design", expanded=not bool(st.session_state.get("validation_study"))),
        st.form("validation_form"),
    ):
        labels = st.multiselect(
            "Validation strategies", list(STRATEGIES), default=["Price + volume"]
        )
        a, b, c = st.columns(3)
        folds = a.selectbox("Chronological folds", [2, 3, 4, 5], index=1)
        capital = b.number_input("Validation starting capital", 1000.0, 1e9, 100000.0, step=10000.0)
        slippage = c.number_input("Validation slippage per side (bps)", 0.0, 500.0, 5.0)
        costs = cost_controls(model, "validation")
        stress = st.checkbox("Also test 2× costs and slippage", value=True)
        st.caption(
            "First 40% of history warms up features; remaining daily bars form disjoint tests. "
            "Each test starts in cash. Buy-and-hold is always included. Fixed default rules; no optimisation."
        )
        run = st.form_submit_button("Run validation study", type="primary", disabled=not labels)
    if run:
        st.session_state.pop("validation_study", None)
        try:
            with st.spinner("Comparing chronological windows in C++…"):
                study = run_validation(
                    dataset,
                    labels,
                    {"initial_capital": capital, "slippage_bps": slippage, **costs},
                    folds=folds,
                    stress=stress,
                )
            st.session_state.validation_study = study
            st.rerun()
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    current = st.session_state.get("validation_study")
    study_tab, history_tab = st.tabs(["Current study", "Saved studies"])
    with study_tab:
        if current:
            render_study(current)
            if st.button("Save validation study", icon=":material/bookmark_add:"):
                if safe_storage(save_study, current):
                    st.toast("Study saved locally.")
        else:
            st.info("Run a study to see fold consistency and cost sensitivity.")
    with history_tab:
        studies = safe_storage(storage.get_setting, "validation_studies", default=[]) or []
        if studies:
            study = st.selectbox(
                "Saved validation study",
                studies,
                format_func=lambda s: f"{s['symbol']} · {s['created_at'][:16]} · {s['id']}",
            )
            st.caption(
                "Saved snapshot; its inputs may differ from the currently selected data. Most recent 10 retained."
            )
            render_study(study, key="saved")
        else:
            st.caption("Save a completed study to retain it across sessions.")


def render_study(study: dict, key: str = "current") -> None:
    st.caption(
        f"{study['symbol']} · {'Synthetic' if study['is_synthetic'] else 'Historical input'} · "
        f"{study['created_at'][:19]} UTC"
    )
    rows = summary_rows(study)
    conditions = list(dict.fromkeys(row["condition"] for row in study["rows"]))
    a, b, c = st.columns(3)
    a.metric("Chronological windows", max(row["fold"] for row in study["rows"]), border=True)
    b.metric("Fixed strategies", len({row["strategy"] for row in study["rows"]}), border=True)
    c.metric("Cost conditions", len(conditions), border=True)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Condition": r["condition"],
                    "Strategy": r["strategy"],
                    "Positive folds": f"{r['positive_folds']} / {r['folds']}",
                    "Beats hold": f"{r['beats_hold_folds']} / {r['folds']}",
                    "Median fold return": percent(r["median_return"]),
                    "Worst fold drawdown": percent(r["worst_drawdown"]),
                }
                for r in rows
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    consistency, details, method = st.tabs(
        ["Consistency chart", "Fold detail", "Method & provenance"]
    )
    with consistency:
        condition = st.selectbox("Chart cost condition", conditions, key="condition_" + key)
        figure = go.Figure()
        for label in dict.fromkeys(row["strategy"] for row in study["rows"]):
            group = [
                r for r in study["rows"] if r["strategy"] == label and r["condition"] == condition
            ]
            figure.add_bar(
                name=label,
                x=[f"Fold {r['fold']}" for r in group],
                y=[r["metrics"]["total_return"] for r in group],
            )
        figure.update_layout(barmode="group", yaxis_tickformat=".1%", yaxis_title="Net fold return")
        figure.add_hline(y=0, line_color=COLORS["muted"], line_width=1)
        st.plotly_chart(chart_layout(figure, height=330), width="stretch", key="fold_chart_" + key)
        st.caption(
            "Independent cash-start periods. These bars are not a cumulative portfolio curve."
        )
    with details:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Condition": r["condition"],
                        "Fold": r["fold"],
                        "Strategy": r["strategy"],
                        "Start": r["evaluation"]["start"],
                        "End": r["evaluation"]["end"],
                        "Net return": percent(r["metrics"]["total_return"]),
                        "Excess vs hold (pp)": number(r["excess_return"] * 100),
                        "Drawdown": percent(r["metrics"]["max_drawdown"]),
                        "Fills": r["metrics"]["trade_count"],
                    }
                    for r in study["rows"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with method:
        st.write(study["method"])
        show_items(study["limitations"])
        st.caption(
            "NSE estimate references: "
            f"[2024 exchange circular]({SOURCES['2024']}) · "
            f"[2026 exchange/IPFT circular]({SOURCES['2026']}) · "
            f"[tax and broker assumptions]({SOURCES['taxes']})"
        )
        st.json(
            {
                "candles_sha256": study["candles_sha256"],
                "settings": study["settings"],
                "first_run": study["rows"][0]["provenance"],
            },
            expanded=False,
        )
    st.download_button(
        "Export validation study",
        json_download(study),
        f"{study['symbol']}_validation.json",
        mime="application/json",
        key="export_" + key,
    )
