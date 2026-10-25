"""Offline comparisons, sensitivity and long-only portfolio research."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import history, storage
from app.assessment import STRATEGIES
from app.computation import load_history
from app.quant_research import (
    cohort_study,
    robustness_study,
    portfolio_study,
    research_report,
    benchmark_diagnostics,
)
from app.research_protocol import visible_candles
from app.ui_helpers import chart_layout, equity_charts, json_download, number, percent
from app.workspace import safe_storage


def show_diagnostics(result: dict) -> None:
    a, b, c = st.columns(3)
    a.metric("Beta to supplied benchmark", number(result.get("beta")), border=True)
    b.metric("Return correlation", number(result.get("correlation")), border=True)
    c.metric("Tracking error / year", percent(result.get("tracking_error")), border=True)
    st.caption(result["assumptions"])
    st.caption(
        "Undefined statistics for flat returns remain unavailable. Buy-and-hold of the same stock is not a broad market index."
    )


def comparison_lab(dataset: dict) -> None:
    ready = history.ready_stocks()
    if not ready:
        st.info("Prepare real histories before comparing stocks.")
        return
    with st.form("cohort_form"):
        selection = st.multiselect(
            "Stocks to compare (up to 8)",
            ready,
            default=[s for s in [dataset["symbol"], "RELIANCE", "TCS"] if s in ready][:3],
            max_selections=8,
        )
        label = st.selectbox(
            "Fixed strategy", [name for name in STRATEGIES if name != "Buy and hold"]
        )
        period = st.date_input(
            "Comparison source window",
            value=(
                date.fromisoformat(visible_candles(dataset)[0]["timestamp"][:10]),
                date.fromisoformat(dataset["candles"][-1]["timestamp"][:10]),
            ),
            max_value=date(2020, 12, 31),
        )
        a, b, c = st.columns(3)
        capital = a.number_input("Comparison initial capital", 1000.0, 1e9, 100000.0)
        commission = b.number_input("Comparison charges per side (bps)", 0.0, 500.0, 10.0)
        slippage = c.number_input("Comparison slippage per side (bps)", 0.0, 500.0, 5.0)
        st.caption(
            "Same source dates and last-30% evaluation for every included stock. Gaps and shorter histories are excluded explicitly. Fixed rules; no winner selection."
        )
        run = st.form_submit_button(
            "Compare fixed strategy across stocks", type="primary", disabled=not selection
        )
    if run:
        st.session_state.pop("cohort_study", None)
        st.session_state.pop("portfolio_study", None)
        try:
            if len(period) != 2:
                raise ValueError("Select both comparison dates.")
            progress = st.progress(0, text="Checking source coverage…")
            study = cohort_study(
                [load_history(s) for s in selection],
                label,
                period[0].isoformat(),
                period[1].isoformat(),
                capital=capital,
                commission=commission,
                slippage=slippage,
                progress=lambda value, message: progress.progress(value, text=message),
            )
            st.session_state.cohort_study = study
            progress.empty()
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    study = st.session_state.get("cohort_study")
    if not study:
        st.info("Submit a comparison to create a fixed research snapshot.")
        return
    st.caption(f"Last submitted study · {study['strategy']} · {study['start']} → {study['end']}")
    if study["excluded"]:
        st.warning(
            f"{len(study['excluded'])} selected stocks excluded. These are part of the result, not silently dropped."
        )
        st.dataframe(pd.DataFrame(study["excluded"]), hide_index=True, width="stretch")
    if not study["rows"]:
        st.info(
            "No stock met the requested coverage. Choose a complete common source window of at least 100 sessions."
        )
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Stock": row["symbol"],
                    "Net return": percent(row["run"]["metrics"]["total_return"]),
                    "Buy & hold": percent(row["benchmark"]["metrics"]["total_return"]),
                    "Excess (pp)": round(
                        100
                        * (
                            row["run"]["metrics"]["total_return"]
                            - row["benchmark"]["metrics"]["total_return"]
                        ),
                        2,
                    ),
                    "Worst fall": percent(row["run"]["metrics"]["max_drawdown"]),
                    "Fills": row["run"]["metrics"]["trade_count"],
                    "Time invested": percent(row["run"]["metrics"]["exposure"]),
                }
                for row in study["rows"]
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    equity, _ = equity_charts({row["symbol"]: row["run"] for row in study["rows"]})
    st.plotly_chart(equity, width="stretch")
    row = st.selectbox("Inspect comparison stock", study["rows"], format_func=lambda r: r["symbol"])
    if st.button("Calculate benchmark exposure"):
        show_diagnostics(benchmark_diagnostics(row["run"], row["benchmark"]))
    st.caption(study["method"])
    st.download_button(
        "Download research report",
        research_report(study),
        "cross_stock_research.md",
        mime="text/markdown",
    )
    st.download_button(
        "Export comparison records",
        json_download(study),
        "cross_stock_research.json",
        mime="application/json",
    )
    if st.button("Save comparison study"):
        items = safe_storage(storage.get_setting, "quant_studies", default=[]) or []
        if (
            safe_storage(storage.set_setting, "quant_studies", [study, *items][:10], default=False)
            is not False
        ):
            st.success("Comparison saved locally.")


def robustness_lab(dataset: dict) -> None:
    results = st.session_state.get("backtests")
    if not results:
        st.info(
            "Run a stock backtest first. This study reuses its exact submitted window and costs."
        )
        return
    if (
        "final" in st.session_state.get("backtest_phase", "").lower()
        and "reserved" not in st.session_state.backtest_phase
    ):
        st.warning(
            "Robustness tuning is disabled for final-period results. Use a development backtest."
        )
        return
    label = st.selectbox("Robustness strategy", list(results))
    st.caption(
        "Inspect nearby settings and 2×/3× costs on the same observations. Results are exploratory; the interface does not choose a best setting."
    )
    if st.button("Run parameter and cost checks", type="primary"):
        st.session_state.pop("parameter_study", None)
        try:
            progress = st.progress(0, text="Checking fixed scenarios…")
            st.session_state.parameter_study = robustness_study(
                st.session_state.get("backtest_dataset", dataset),
                label,
                st.session_state.experiment_settings,
                progress=lambda value, message: progress.progress(value, text=message),
            )
            progress.empty()
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    study = st.session_state.get("parameter_study")
    if not study:
        return
    st.caption(f"Last submitted sensitivity · {study['symbol']} · {study['strategy']}")
    rows = [
        {
            "Case": r["case"],
            "Lookback": r["lookback"],
            "Volume threshold": r["volume_threshold"],
            "Cost multiple": r["cost_multiplier"],
            "Net return": percent(r["metrics"]["total_return"]),
            "Worst fall": percent(r["metrics"]["max_drawdown"]),
            "Fills": r["metrics"]["trade_count"],
        }
        for r in study["rows"]
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    grid = [r for r in study["rows"] if r["case"] == "Parameter grid"]
    frame = pd.DataFrame(
        [
            {
                "lookback": r["lookback"],
                "volume": r["volume_threshold"],
                "return": r["metrics"]["total_return"],
            }
            for r in grid
        ]
    ).pivot(index="volume", columns="lookback", values="return")
    fig = go.Figure(
        go.Heatmap(
            x=list(frame.columns),
            y=list(frame.index),
            z=frame.values,
            colorscale="BrBG",
            zmid=0,
            colorbar=dict(tickformat=".0%"),
        )
    )
    fig.update_layout(xaxis_title="Structure lookback", yaxis_title="Relative-volume threshold")
    st.plotly_chart(chart_layout(fig, height=300), width="stretch")
    st.caption(study["method"])
    st.download_button(
        "Export parameter sensitivity", json_download(study), "parameter_sensitivity.json"
    )


def portfolio_lab() -> None:
    study = st.session_state.get("cohort_study")
    if not study or not study["rows"]:
        st.info(
            "Create a Stock comparison first so every portfolio sleeve uses identical dates and costs."
        )
        return
    symbols = [r["symbol"] for r in study["rows"]]
    with st.form("portfolio_form"):
        st.caption(
            "Initial allocations to the comparison's net strategy curves. Long-only, no leverage or rebalancing. Unallocated money remains cash."
        )
        capital = st.number_input("Portfolio starting capital", 1000.0, 1e9, 100000.0)
        cap = st.slider("Maximum initial allocation per stock (%)", 10, 100, 60, 5)
        weights = {
            symbol: st.number_input(
                f"{symbol} initial allocation (%)",
                0.0,
                100.0,
                min(float(cap), 100.0 / len(symbols)),
                key="weight_" + symbol,
            )
            / 100
            for symbol in symbols
        }
        run = st.form_submit_button("Evaluate portfolio risk", type="primary")
    if run:
        st.session_state.pop("portfolio_study", None)
        try:
            st.session_state.portfolio_study = portfolio_study(study, weights, capital, cap / 100)
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    result = st.session_state.get("portfolio_study")
    if not result:
        return
    portfolios = result["portfolios"]
    current = portfolios["Strategy portfolio"]
    a, b, c = st.columns(3)
    a.metric("Portfolio net return", percent(current["metrics"]["total_return"]), border=True)
    b.metric("Worst historical fall", percent(current["metrics"]["max_drawdown"]), border=True)
    c.metric("Initial unallocated cash", percent(current["cash_weight"]), border=True)
    equity, drawdown = equity_charts(portfolios)
    st.plotly_chart(equity, width="stretch")
    st.plotly_chart(drawdown, width="stretch")
    st.dataframe(pd.DataFrame(current["weights"]), hide_index=True, width="stretch")
    fig = go.Figure(
        go.Heatmap(
            x=list(result["weights"]),
            y=list(result["weights"]),
            z=current["correlations"],
            zmin=-1,
            zmax=1,
            colorscale="BrBG",
        )
    )
    st.plotly_chart(chart_layout(fig, height=330), width="stretch")
    st.caption(
        "Correlation of net strategy sleeve returns. Flat-return correlations are unavailable, rather than zero."
    )
    show_diagnostics(result["diagnostics"])
    st.caption(current["assumptions"])
    st.download_button("Export portfolio study", json_download(result), "portfolio_research.json")


def quant_workspace(dataset: dict) -> None:
    st.write(
        "Compare fixed rules, challenge assumptions and examine portfolio risk using the local C++ engine."
    )
    section = st.radio(
        "Quant research view",
        ["Stock comparison", "Robustness", "Portfolio", "Saved studies"],
        horizontal=True,
    )
    if section == "Stock comparison":
        comparison_lab(dataset)
    elif section == "Robustness":
        robustness_lab(dataset)
    elif section == "Portfolio":
        portfolio_lab()
    else:
        items = safe_storage(storage.get_setting, "quant_studies", default=[]) or []
        if not items:
            st.info("Save a comparison study to reopen it here. The latest 10 are retained.")
        else:
            study = st.selectbox(
                "Saved quant study",
                items,
                format_func=lambda s: (
                    f"{s['strategy']} · {s['start']} → {s['end']} · {len(s['rows'])} stocks"
                ),
            )
            if st.button("Use saved comparison for portfolio research"):
                st.session_state.cohort_study = study
                st.session_state.pop("portfolio_study", None)
                st.success("Loaded. Open Portfolio to choose allocations.")
            st.download_button(
                "Download saved research report", research_report(study), "saved_quant_report.md"
            )
