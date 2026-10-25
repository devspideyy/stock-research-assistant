"""Monte Carlo attached to a submitted stock/strategy backtest, without double fees."""

import hashlib
import json

import streamlit as st
import pandas as pd

from app.computation import calculate
from app.sensitivity import risk_sensitivity
from app.research_protocol import record_run
from app.ui_helpers import json_download, number, percent, simulation_chart, terminal_distribution


def strategy_risk(
    dataset: dict, results: dict, settings: dict, *, label: str | None = None
) -> None:
    st.markdown("### Strategy risk, in context")
    st.caption(
        "Explore possible investment outcomes from this strategy's historical net returns. "
        "Cash days and submitted costs are included."
    )
    if settings.get("session_gaps_present"):
        st.warning(
            "Daily-return Monte Carlo is withheld for gap-overridden runs. Choose a complete evaluation window first."
        )
        return
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "symbol": dataset["symbol"],
                "settings": settings,
                "requests": [run["_provenance"] for run in results.values()],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if st.session_state.get("strategy_risk_input") != fingerprint:
        st.session_state.pop("strategy_simulation", None)
        st.session_state.pop("risk_sensitivity", None)
        st.session_state.strategy_risk_input = fingerprint
    previous = st.session_state.get("strategy_simulation", {})
    defaults = previous.get("_provenance", {}).get("options", {})
    if (
        label
        and previous.get("strategy_calibration", {}).get("strategy") != results[label]["strategy"]
    ):
        defaults = {}
    with st.form("strategy_risk_form"):
        a, b, c = st.columns(3)
        if label is None:
            label = a.selectbox("Risk strategy", list(results))
        else:
            a.markdown(f"**Strategy**\n\n{label}")
        horizon = b.number_input(
            "Risk horizon (daily observations)", 2, 504, defaults.get("horizon", 126)
        )
        paths = c.selectbox(
            "Risk simulation paths",
            [500, 1000, 5000],
            index=[500, 1000, 5000].index(defaults.get("paths", 1000)),
        )
        with st.expander("Advanced simulation settings"):
            a, b, c = st.columns(3)
            block = a.number_input("Return block length", 1, 60, defaults.get("block_size", 5))
            seed = b.number_input("Risk seed", 0, 2147483647, defaults.get("seed", 42))
            loss = c.slider(
                "Drawdown level to inspect (%)",
                5,
                90,
                round(defaults.get("drawdown_threshold", 0.2) * 100),
                5,
            )
        run = st.form_submit_button("Simulate strategy risk", type="primary")
    if run:
        st.session_state.pop("strategy_simulation", None)
        st.session_state.pop("risk_sensitivity", None)
        try:
            with st.spinner("Resampling net strategy returns in C++…"):
                result = calculate(
                    "simulate",
                    dataset["candles"],
                    **settings,
                    strategy=results[label]["strategy"],
                    basis="strategy",
                    method="bootstrap",
                    capital=settings.get("initial_capital", 100000),
                    horizon=int(horizon),
                    paths=int(paths),
                    block_size=int(block),
                    seed=int(seed),
                    drawdown_threshold=loss / 100,
                )
            result["linked_backtest"] = results[label]["_provenance"]
            result["symbol"] = dataset["symbol"]
            result["is_synthetic"] = dataset["is_synthetic"]
            st.session_state.strategy_simulation = result
            record_run(
                "strategy_risk", dataset, result["_provenance"]["options"], result["summary"]
            )
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    result = st.session_state.get("strategy_simulation")
    if not result:
        st.info("Run a strategy-risk study after submitting the backtest above.")
        return
    calibration = result["strategy_calibration"]
    if calibration["strategy"] != results[label]["strategy"]:
        st.info("The displayed strategy changed. Run its risk study to see matching results.")
        return
    st.caption(
        f"{result['symbol']} · {label} · "
        f"{calibration['evaluation']['start']} → {calibration['evaluation']['end']} · "
        "Last submitted simulation; change inputs and submit to update."
    )
    a, b, c, d = st.container(key="risk_metrics").columns(4)
    a.metric("Median ending investment", number(result["summary"]["p50"], prefix="₹ "), border=True)
    b.metric(
        "Scenarios ending in loss",
        percent(result["summary"]["probability_loss"]),
        border=True,
        help="Share of simulated paths ending below the starting investment, under these assumptions.",
    )
    c.metric(
        "Severe simulated fall",
        percent(result["summary"]["max_drawdown_p95"]),
        border=True,
        help="95th percentile of the largest peak-to-trough fall in each simulated path.",
    )
    threshold = result["_provenance"]["options"]["drawdown_threshold"]
    d.metric(
        f"Drawdown ≥ {threshold:.0%}",
        percent(result["summary"]["probability_drawdown"]),
        border=True,
    )
    if not calibration["metrics"]["trade_count"]:
        st.warning(
            "This rule made no fills in calibration. Flat cash simulations do not establish low future strategy risk."
        )
    observations = result["calibration"]["observations"]
    st.caption(
        f"Calibration: {observations} net daily returns · {calibration['metrics']['trade_count']} fills · "
        "Cash days and costs included. Percentiles are conditional scenarios, not guarantees."
    )
    if observations < 252:
        st.warning(
            "Less than one trading year of calibration. More simulated paths do not add historical evidence."
        )
    replay = st.toggle("Animate Monte Carlo paths", value=False)
    st.plotly_chart(
        simulation_chart(result, replay=replay), width="stretch", key="linked_strategy_paths"
    )
    with st.expander("Terminal distribution and method"):
        st.caption(
            "Block bootstrap resamples net daily returns. Entry and exit signals are not "
            "recalculated on new synthetic stock prices."
        )
        st.plotly_chart(
            terminal_distribution(result), width="stretch", key="linked_strategy_distribution"
        )
        st.caption(
            f"Submitted drawdown reference: {threshold:.0%}. Reported percentiles describe the submitted simulation; "
            "they are not guaranteed future loss bounds. Costs are already in daily returns and are not deducted twice."
        )
        st.json(
            {
                "calibration": calibration,
                "provenance": result["_provenance"],
                "linked_backtest": result["linked_backtest"],
            },
            expanded=False,
        )
    st.download_button(
        "Export linked strategy risk",
        json_download(result),
        f"{dataset['symbol']}_strategy_risk.json",
        mime="application/json",
    )
    with st.expander("Block length, calibration-window and cost sensitivity"):
        st.caption(
            "Seven fixed scenarios, one factor at a time. Short windows use the tail of the same backtest's net returns. Cost stresses are assumptions, not future fee forecasts."
        )
        if st.button("Run strategy risk sensitivity"):
            try:
                with st.spinner("Comparing calibration windows, blocks and execution stresses…"):
                    st.session_state.risk_sensitivity = risk_sensitivity(
                        dataset,
                        settings,
                        result["strategy_calibration"]["strategy"],
                        paths=500,
                        horizon=result["_provenance"]["options"]["horizon"],
                        seed=result["seed"],
                    )
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(str(exc))
        sensitivity = st.session_state.get("risk_sensitivity")
        if sensitivity:
            st.caption(
                f"Saved sensitivity snapshot · {sensitivity['symbol']} · {sensitivity['strategy']}"
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            k: r[k]
                            for k in [
                                "scenario",
                                "block",
                                "cost_multiplier",
                                "observations",
                                "p05",
                                "p50",
                                "p95",
                                "probability_loss",
                                "max_drawdown_p95",
                            ]
                        }
                        for r in sensitivity["rows"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            st.download_button(
                "Export risk sensitivity",
                json_download(sensitivity),
                "risk_sensitivity.json",
                mime="application/json",
            )
