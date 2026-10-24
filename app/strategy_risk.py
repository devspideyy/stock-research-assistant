"""Monte Carlo attached to a submitted stock/strategy backtest, without double fees."""

import hashlib
import json

import streamlit as st

from app.engine_bridge import EngineClient
from app.ui_helpers import json_download, number, percent, simulation_chart, terminal_distribution


def strategy_risk(dataset: dict, results: dict, settings: dict) -> None:
    st.markdown("### Strategy risk, in context")
    st.caption(
        "Block-bootstrap the selected strategy's net daily equity returns, including cash days. "
        "This estimates conditional variability; signals are not recalculated on synthetic price paths."
    )
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
        st.session_state.strategy_risk_input = fingerprint
    with st.form("strategy_risk_form"):
        a, b, c = st.columns(3)
        label = a.selectbox(
            "Risk strategy",
            list(results),
            index=list(results).index("Buy and hold") if "Buy and hold" in results else 0,
        )
        horizon = b.number_input("Risk horizon (daily observations)", 2, 504, 126)
        paths = c.selectbox("Risk simulation paths", [500, 1000, 5000], index=1)
        a, b, c = st.columns(3)
        block = a.number_input("Return block length", 1, 60, 5)
        seed = b.number_input("Risk seed", 0, 2147483647, 42)
        loss = c.slider("Drawdown level to inspect (%)", 5, 90, 20, 5)
        run = st.form_submit_button("Simulate strategy risk", type="primary")
    if run:
        st.session_state.pop("strategy_simulation", None)
        try:
            with st.spinner("Resampling net strategy returns in C++…"):
                result = EngineClient().simulate(
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
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    result = st.session_state.get("strategy_simulation")
    if not result:
        st.info("Run a strategy-risk study after submitting the backtest above.")
        return
    calibration = result["strategy_calibration"]
    st.caption(
        f"{result['symbol']} · {calibration['strategy']} · "
        f"{calibration['evaluation']['start']} → {calibration['evaluation']['end']} · "
        "Last submitted simulation; change inputs and submit to update."
    )
    a, b, c, d = st.columns(4)
    a.metric("Median terminal wealth", number(result["summary"]["p50"]), border=True)
    b.metric(
        "Conditional terminal loss", percent(result["summary"]["probability_loss"]), border=True
    )
    c.metric(
        "95th-percentile drawdown", percent(result["summary"]["max_drawdown_p95"]), border=True
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
    st.plotly_chart(
        simulation_chart(result, replay=True), width="stretch", key="linked_strategy_paths"
    )
    with st.expander("Terminal distribution and method"):
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
