"""A readable result summary, optional detail panels and complete saved experiments."""

import pandas as pd
import streamlit as st

from app import experiments
from app.evaluation_ui import benchmark_panel, final_protocol_panel, journal_panel
from app.experiment_ui import accounting_view, import_backtest_for_validation
from app.strategy_risk import strategy_risk
from app.ui_helpers import equity_charts, json_download, number, percent
from app.quant_research import benchmark_diagnostics
from app.quant_workspace import show_diagnostics
from app.workspace import safe_storage, go_stock_section as go_section


def selected_strategy(results: dict) -> str:
    labels = list(results)
    previous = st.session_state.get("active_strategy")
    label = st.selectbox(
        "Selected strategy",
        labels,
        index=labels.index(previous) if previous in labels else 0,
        key="result_strategy",
    )
    st.session_state.active_strategy = label
    return label


def open_backtest_chart() -> None:
    st.session_state.chart_workspace = "Research chart"
    go_section("Chart & indicators")


def experiment_actions(dataset: dict, results: dict, settings: dict, *, risk_page=False) -> None:
    save, risk = st.columns([1, 1])
    if save.button(
        "Save complete experiment",
        icon=":material/bookmark:",
        width="stretch",
        type="primary" if risk_page else "secondary",
    ):
        simulation = st.session_state.get("strategy_simulation")
        if simulation and simulation.get("linked_backtest") not in [
            result["_provenance"] for result in results.values()
        ]:
            simulation = None
        identifier = safe_storage(
            experiments.save_experiment,
            dataset,
            results,
            settings,
            backtest_dataset=st.session_state.get("backtest_dataset", dataset),
            phase=st.session_state.get("backtest_phase", "exploratory"),
            run_id=st.session_state.get("backtest_run_id"),
            active_strategy=st.session_state.get("active_strategy"),
            strategy_simulation=simulation,
            strategy_risk_input=st.session_state.get("strategy_risk_input"),
        )
        if identifier:
            st.success("Saved with source prices, settings, results and any linked risk study.")
    risk.button(
        "Back to backtest" if risk_page else "Explore Monte Carlo risk",
        type="secondary" if risk_page else "primary",
        width="stretch",
        icon=":material/ssid_chart:",
        on_click=go_section,
        args=("Strategies & backtest" if risk_page else "Risk / Monte Carlo",),
    )
    st.button(
        "View entries & exits on research chart", on_click=open_backtest_chart, width="stretch"
    )


def backtest_results(dataset: dict, results: dict, settings: dict) -> None:
    st.divider()
    st.caption("RESULTS / LAST SUBMITTED EXPERIMENT")
    label = selected_strategy(results)
    result = results[label]
    metrics = result["metrics"]
    capital = settings.get("initial_capital", 100000)
    ending = result["equity"][-1]["equity"]
    hold = results.get("Buy and hold", {}).get("metrics", {}).get("total_return")
    excess = metrics["total_return"] - hold if hold is not None else None
    cards = st.container(key="backtest_metrics").columns(4)
    cards[0].metric("Ending investment", number(ending, prefix="₹ "), border=True)
    cards[1].metric(
        "Net profit / loss",
        number(ending - capital, prefix="₹ "),
        delta=percent(metrics["total_return"]),
        delta_color="off",
        border=True,
    )
    cards[2].metric("Worst historical fall", percent(metrics["max_drawdown"]), border=True)
    cards[3].metric(
        "Versus buy & hold",
        f"{excess * 100:+.2f} pp" if excess is not None else "Not compared",
        border=True,
        help="Difference in net return, in percentage points, on the same window.",
    )
    evaluation = result["evaluation"]
    st.write(
        f"Starting with **{number(capital, prefix='₹ ')}**, this rule ended at "
        f"**{number(ending, prefix='₹ ')}** after the submitted costs. "
        f"Its largest fall from an earlier portfolio peak was **{percent(metrics['max_drawdown'])}**."
    )
    st.caption(
        f"{dataset['symbol']} · {evaluation['start']} → {evaluation['end']} · "
        f"{evaluation['bars']} evaluated daily bars · {metrics['trade_count']} fills · "
        f"{st.session_state.get('backtest_phase', 'exploratory')} · Historical, not live"
    )
    if not metrics["trade_count"]:
        st.info(
            "This rule made no trades in this window. A flat cash result is not evidence of low risk."
        )
    experiment_actions(dataset, results, settings)
    view = st.radio(
        "Result view",
        ["Summary", "Equity & replay", "Trades", "Benchmark", "Advanced"],
        horizontal=True,
        key="backtest_result_view",
        label_visibility="collapsed",
    )
    if view == "Summary":
        st.subheader("Compare with the benchmark")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Strategy": name,
                        "Net return": run["metrics"]["total_return"],
                        "Worst fall": run["metrics"]["max_drawdown"],
                        "Fills": run["metrics"]["trade_count"],
                    }
                    for name, run in results.items()
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Net return": st.column_config.NumberColumn(format="percent"),
                "Worst fall": st.column_config.NumberColumn(format="percent"),
            },
        )
        comparison = {name: run for name, run in results.items() if name in {label, "Buy and hold"}}
        equity, _ = equity_charts(comparison)
        st.plotly_chart(equity, width="stretch", config={"displaylogo": False})
        st.caption("Net portfolio value, including cash and marked-to-market open positions.")
        st.button(
            "Challenge these rules in Validation",
            icon=":material/fact_check:",
            on_click=import_backtest_for_validation,
        )
    elif view == "Equity & replay":
        replay = st.toggle("Animated backtest replay", value=False)
        st.caption("Optional playback of the completed run. Calculations retain every observation.")
        comparison = {name: run for name, run in results.items() if name in {label, "Buy and hold"}}
        equity, drawdown = equity_charts(comparison, replay=replay)
        st.plotly_chart(equity, width="stretch")
        st.plotly_chart(drawdown, width="stretch")
    elif view == "Trades":
        accounting_view(result)
        if result.get("trades"):
            st.dataframe(pd.DataFrame(result["trades"]), hide_index=True, width="stretch")
        else:
            st.info("No executed trades for this strategy.")
    elif view == "Benchmark":
        if "Buy and hold" in results:
            show_diagnostics(benchmark_diagnostics(result, results["Buy and hold"]))
        else:
            st.info("Run a comparison with buy-and-hold to inspect benchmark exposure.")
    else:
        st.caption("Detailed statistics and audit tools for the submitted experiment.")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Measure": name.replace("_", " ").title(), "Value": str(value)}
                    for name, value in metrics.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        benchmark_panel(st.session_state.get("backtest_dataset", dataset), results)
        final_protocol_panel(dataset, results, settings)
        journal_panel()
        with st.expander("Execution assumptions"):
            st.json(settings, expanded=False)
            st.write(result.get("assumptions", []))
        st.download_button(
            "Download backtest records",
            json_download(
                {
                    "symbol": dataset["symbol"],
                    "is_synthetic": dataset["is_synthetic"],
                    "data_fingerprint": st.session_state.dataset_fingerprint,
                    "settings": settings,
                    "results": results,
                }
            ),
            file_name=f"{dataset['symbol']}_backtests.json",
            mime="application/json",
        )


def risk_workspace(dataset: dict, stock_scenarios) -> None:
    st.subheader("Monte Carlo")
    st.caption("Explore a range of conditional outcomes for this stock or a submitted strategy.")
    focus = st.radio(
        "Simulation focus",
        ["Backtested strategy", "Stock price scenarios"],
        horizontal=True,
    )
    if focus == "Stock price scenarios":
        stock_scenarios(dataset)
        return
    results = st.session_state.get("backtests")
    if not results:
        st.info(
            "First run a backtest. Its net returns, cash days and costs will calibrate strategy risk."
        )
        st.button(
            "Set up a backtest",
            type="primary",
            on_click=go_section,
            args=("Strategies & backtest",),
        )
        st.caption("You can also choose Stock price scenarios above without running a strategy.")
        return
    label = selected_strategy(results)
    strategy_risk(
        st.session_state.get("backtest_dataset", dataset),
        results,
        st.session_state.experiment_settings,
        label=label,
    )
    experiment_actions(dataset, results, st.session_state.experiment_settings, risk_page=True)


def open_experiment(identifier: str) -> None:
    try:
        snapshot = safe_storage(experiments.load_experiment, identifier)
    except ValueError as exc:
        st.error(str(exc))
        return
    if snapshot:
        st.session_state.active_snapshot = snapshot
        st.session_state.restore_snapshot = True
        st.session_state.data_source = "Saved experiment"
        st.session_state.backtest_cost_model = (
            "NSE delivery estimate"
            if snapshot["settings"].get("cost_schedule")
            else "Hypothetical bps"
        )
        st.session_state.backtest_commission = float(snapshot["settings"].get("commission_bps", 10))
        go_section("Strategies & backtest")


def saved_experiments() -> None:
    records = safe_storage(experiments.list_experiments, default=[]) or []
    if not records:
        st.info(
            "Save a complete experiment after a backtest to reopen it here, even after restarting."
        )
        return
    record = st.selectbox(
        "Saved experiment",
        records,
        format_func=lambda row: f"{row['symbol']} · {row['created_at'][:19]} UTC · {row['id'][:8]}",
    )
    st.caption(
        "Reopening uses the saved price snapshot and settings, rather than recalculating on a different source."
    )
    st.button(
        "Reopen complete experiment",
        type="primary",
        on_click=open_experiment,
        args=(record["id"],),
    )
