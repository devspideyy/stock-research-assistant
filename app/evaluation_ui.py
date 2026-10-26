"""Compact experiment context, source health, protocol controls and research evaluation."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.engine_bridge import EngineClient
from app.evaluation import sector_reference, evaluate_ratings
from app.research_protocol import (
    quality_report,
    frozen_policy,
    freeze_policy,
    apply_policy,
    require_quality,
    record_run,
    run_history,
    latest_complete_window,
)
from app.ui_helpers import chart_layout, percent, json_download
from app.workspace import safe_storage


def use_complete_window(dataset: dict) -> None:
    selected = latest_complete_window(dataset, minimum=30)
    start = selected["candles"][selected["window_start"]]["timestamp"][:10]
    st.session_state["period_" + dataset["symbol"]] = (
        date.fromisoformat(start),
        date.fromisoformat(dataset["candles"][-1]["timestamp"][:10]),
    )


def source_health(dataset: dict) -> None:
    report = quality_report(dataset)
    with st.expander("Data quality and price basis"):
        st.caption(
            "Adjusted research units"
            if dataset.get("price_basis") == "adjusted"
            else "Raw / source units"
        )
        st.caption(
            f"{len(report['omitted_invalid'])} known invalid observations · "
            f"{len(report['missing_reference_sessions'])} missing reference sessions · "
            f"{len(report['long_gaps'])} gaps longer than 10 calendar days."
        )
        st.caption(
            f"{dataset.get('window_start', 0):,} pre-window bars retained for causal feature warm-up. Evaluation and stock-scenario calibration exclude those earlier bars."
        )
        st.json(report, expanded=False)
        st.caption(
            "The session reference is a frozen observed-market proxy. It does not certify listing identity, suspensions, action completeness or exchange holidays."
        )
    if not report["eligible"] and dataset.get("history_quality"):
        st.info(
            "This window crosses missing or invalid sessions. Use a complete window for backtests and daily-return risk studies."
        )
        if (
            len(
                [
                    c
                    for c in dataset["candles"]
                    if c["timestamp"][:10]
                    > max(
                        report["omitted_invalid"]
                        + report["missing_reference_sessions"]
                        + [g["before"] for g in report["long_gaps"]]
                    )
                ]
            )
            >= 30
        ):
            st.button("Use latest complete window", on_click=use_complete_window, args=(dataset,))


def experiment_context() -> None:
    results = st.session_state.get("backtests")
    if results:
        run = next(iter(results.values()))
        with st.expander("Last submitted experiment · fixed snapshot"):
            st.caption(
                f"{run['evaluation']['start']} → {run['evaluation']['end']} · {len(results)} strategies · Run {st.session_state.get('backtest_run_id', 'unrecorded')}"
            )
            st.json(st.session_state.get("experiment_settings", {}), expanded=False)


def final_protocol_panel(dataset: dict, results: dict, settings: dict) -> None:
    with st.expander("Reserve and evaluate a frozen final period"):
        policy = safe_storage(frozen_policy, dataset)
        if not policy:
            st.caption(
                "Reserve the last 20% for a locked policy. Subsequent development runs exclude it. Locking cannot undo earlier viewing; the journal records future accesses."
            )
            attested = st.checkbox(
                "I have not inspected the proposed final-period outcomes", value=False
            )
            enough_history = len(dataset["candles"]) - dataset.get("window_start", 0) >= 100
            if not enough_history:
                st.caption("Choose at least 100 observations to reserve a final period.")
            if st.button("Freeze final-period policy", disabled=not enough_history):
                if safe_storage(freeze_policy, dataset, settings, list(results), attested):
                    st.rerun()
        else:
            st.caption(
                f"Reserved: {policy['start']} → {policy['end']} · Prior non-inspection {'attested by user' if policy['untouched_attested'] else 'unconfirmed'}"
            )
            st.json(policy, expanded=False)
            if st.button("Run frozen final-period test", type="primary"):
                try:
                    effective, options, phase = apply_policy(
                        dataset, policy["settings"], policy["strategies"], final=True
                    )
                    quality = require_quality(effective, options)
                    options["session_gaps_present"] = not quality["eligible"]
                    record_run("final_test_attempt", dataset, options, {"phase": phase})
                    engine = EngineClient()
                    from app.assessment import STRATEGIES

                    with st.spinner("Evaluating the frozen final policy…"):
                        runs = {
                            label: engine.backtest(
                                effective["candles"], strategy=STRATEGIES[label], **options
                            )
                            for label in policy["strategies"]
                        }
                    identifier = record_run(
                        "final_test",
                        dataset,
                        options,
                        {"phase": phase, "metrics": {k: v["metrics"] for k, v in runs.items()}},
                    )
                    st.session_state.update(
                        backtests=runs,
                        backtest_dataset=effective,
                        experiment_settings=options,
                        backtest_run_id=identifier,
                        backtest_phase=phase,
                    )
                    st.session_state.pop("sector_context", None)
                    st.rerun()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.error(str(exc))


def benchmark_panel(dataset: dict, results: dict) -> None:
    with st.expander("Benchmark and sector context"):
        if "Buy and hold" in results:
            hold = results["Buy and hold"]["metrics"]["total_return"]
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Strategy": k,
                            "Net return": percent(v["metrics"]["total_return"]),
                            "Excess vs equally costed hold (pp)": round(
                                100 * (v["metrics"]["total_return"] - hold), 3
                            ),
                        }
                        for k, v in results.items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        st.caption(
            "Costed buy-and-hold is the primary comparison. Sector context is a separate gross reference, not a claim of investable alpha."
        )
        if st.button("Calculate sector cohort context"):
            try:
                st.session_state.sector_context = sector_reference(
                    dataset, next(iter(results.values()))
                )
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(str(exc))
        context = st.session_state.get("sector_context")
        if context:
            if context["available"]:
                st.caption(context["method"])
                figure = go.Figure(
                    go.Scatter(x=context["dates"], y=context["growth"], name="Gross sector cohort")
                )
                st.plotly_chart(chart_layout(figure, height=280), width="stretch")
                st.write("Peers: " + ", ".join(p["symbol"] for p in context["peers"]))
            else:
                st.info(context["reason"])


def rating_panel(dataset: dict) -> None:
    with st.expander("Evaluate the rating hypotheses on development history"):
        st.caption(
            "Test the manual score weights against later stock returns. The final 20% stays excluded. Results are descriptive, not calibrated buy/sell probabilities."
        )
        horizon = st.selectbox("Rating label horizon", [10, 21, 42], index=1)
        if st.button("Evaluate historical rating cases"):
            try:
                with st.spinner("Evaluating prefix-only price-evidence snapshots…"):
                    st.session_state.rating_evaluation = evaluate_ratings(dataset, horizon)
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(str(exc))
        result = st.session_state.get("rating_evaluation")
        if result:
            st.caption(
                f"{result['symbol']} · Development ends {result['development_end']} · Baseline positive-return fraction {percent(result['baseline_positive_fraction'])}"
            )
            st.dataframe(pd.DataFrame(result["groups"]), hide_index=True, width="stretch")
            st.caption(result["limitations"])
            st.download_button(
                "Export rating evaluation",
                json_download(result),
                "rating_evaluation.json",
                mime="application/json",
            )


def journal_panel() -> None:
    with st.expander("Experiment journal · including failed final-test attempts"):
        records = safe_storage(run_history, 100, default=[]) or []
        st.caption(
            "Most recent 100 records. Final-period locks are immutable for the same source/window. Previous inspection cannot be erased by creating a lock."
        )
        st.dataframe(
            pd.DataFrame(
                [{k: r[k] for k in ["id", "kind", "created_at", "symbol"]} for r in records]
            ),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Export experiment journal",
            json_download(records),
            "experiment_journal.json",
            mime="application/json",
        )
