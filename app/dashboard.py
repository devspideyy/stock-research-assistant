"""Python workstation UI for the independently compiled C++ research engine.

Start from the repository root: python -m streamlit run app/dashboard.py
Every expensive engine or model operation requires an explicit user action.
"""

# ruff: noqa: E402 -- Streamlit runs a file path; establish the project import root first.

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

# Streamlit executes this file by path; make the local package importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app import storage
from app.attachments import load_evidence_json
from app.chat import answer_question
from app.demo import SYMBOLS, load_demo
from app.engine_bridge import EngineClient, load_candles_csv
from app.monitor import run_once
from app.research_labs import indicator_lab, stock_catalogue
from app.services import build_evidence, generate_report
from app.ui_helpers import (
    candle_frame,
    depth_chart,
    equity_charts,
    json_download,
    number,
    percent,
    plain_text,
    price_chart,
    render_evidence,
    render_report,
    show_items,
    simulation_chart,
)


st.set_page_config(
    page_title="Equity Research Workstation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

RESULT_KEYS = (
    "analysis",
    "evidence",
    "report",
    "backtests",
    "simulation",
    "depth_result",
    "chat_history",
    "experiment_settings",
    "indicator_result",
)
STRATEGIES = {
    "Price + volume": "price_volume",
    "Buy and hold": "buy_hold",
    "Indicator baseline": "indicator",
}


def engine_request(operation: str, *args, **kwargs) -> dict | None:
    try:
        with st.spinner("Running the C++ engine…"):
            return getattr(EngineClient(), operation)(*args, **kwargs)
    except (RuntimeError, ValueError, OSError) as exc:
        st.error(str(exc))
        st.caption("Compile the engine with the setup instructions in README.md, then retry.")
        return None


def safe_storage(callable_, *args, default=None, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except (RuntimeError, OSError, sqlite3.Error) as exc:
        st.warning(f"Local storage is unavailable: {exc}")
        return default


def model_controls() -> tuple[str, str | None]:
    st.sidebar.divider()
    st.sidebar.markdown("### Research assistant")
    label = st.sidebar.selectbox(
        "Analysis provider",
        ["Rules · no model required", "OpenRouter · free routes only", "Ollama · local model"],
        key="provider_label",
    )
    provider = {
        "Rules · no model required": "rules",
        "OpenRouter · free routes only": "openrouter",
        "Ollama · local model": "ollama",
    }[label]
    model = None
    if provider == "openrouter":
        model = st.sidebar.text_input(
            "Free model ID",
            value=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            help="Only the free router or a currently verified :free model is allowed.",
        )
        st.sidebar.caption(
            "Key configured"
            if os.getenv("OPENROUTER_API_KEY")
            else "Set OPENROUTER_API_KEY locally before making a request."
        )
        usage = safe_storage(storage.usage_summary, default={}) or {}
        if usage:
            st.sidebar.caption(
                f"Local daily budget: {usage.get('used', 0)} used / "
                f"{usage.get('daily_limit', '?')} limit"
            )
    elif provider == "ollama":
        model = st.sidebar.text_input(
            "Installed model name", value=os.getenv("OLLAMA_MODEL", "qwen3:4b")
        )
        st.sidebar.caption("Requires a running local Ollama server; GPU optional.")
    else:
        st.sidebar.caption("Deterministic explanations work offline. Generative AI is optional.")
    st.sidebar.caption("Models run only when you request a report or send a question.")
    return provider, model


def select_dataset() -> dict:
    st.sidebar.markdown("## Research workspace")
    st.sidebar.caption("INDIA FIRST · CASH EQUITIES")
    source = st.sidebar.radio("Data source", ["Synthetic demo", "Upload historical CSV"])
    if source == "Synthetic demo":
        symbol = st.sidebar.selectbox("Demonstration instrument", SYMBOLS)
        dataset = load_demo(symbol)
    else:
        symbol = st.sidebar.text_input("Instrument label", value="MY_NSE_STOCK").strip().upper()
        uploaded = st.sidebar.file_uploader("Historical OHLCV CSV", type=["csv"])
        st.sidebar.caption(
            "Required: Date/Timestamp, Open, High, Low, Close, Volume. "
            "Use consistent, documented corporate-action adjustments."
        )
        if uploaded is None:
            st.title("Equity Research Workstation")
            st.info("Upload a historical OHLCV file to begin, or select the synthetic demo.")
            st.stop()
        try:
            candles = load_candles_csv(uploaded.getvalue())
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(f"CSV validation failed: {exc}")
            st.stop()
        dataset = {
            "symbol": symbol or "UPLOADED_STOCK",
            "candles": candles,
            "news": [],
            "fundamentals": {},
            "depth": {},
            "is_synthetic": False,
            "description": f"User-supplied historical file: {uploaded.name}",
        }
        attachment = st.sidebar.file_uploader(
            "Optional dated evidence JSON", type=["json"], key="evidence_attachment"
        )
        st.sidebar.caption(
            "Attach sourced news, published company figures or a separately dated depth snapshot. See README for the format."
        )
        if attachment is not None:
            try:
                dataset.update(load_evidence_json(attachment.getvalue()))
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                st.error(f"Evidence attachment rejected: {exc}")
                st.stop()
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "symbol": dataset["symbol"],
                "candles": dataset["candles"],
                "synthetic": dataset["is_synthetic"],
                "news": dataset.get("news"),
                "fundamentals": dataset.get("fundamentals"),
                "depth": dataset.get("depth"),
            },
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    if st.session_state.get("dataset_fingerprint") != fingerprint:
        for key in RESULT_KEYS:
            st.session_state.pop(key, None)
        st.session_state.dataset_fingerprint = fingerprint
    return dataset


def overview(dataset: dict, provider: str, model: str | None) -> None:
    candles = dataset["candles"]
    last = candles[-1]
    st.markdown("### An inspectable research decision")
    st.write(
        "Start with price structure, volume, dated events and the information that is missing. "
        "Supporting indicators provide context. Short-horizon liquidity is kept separate from investment research."
    )
    cols = st.columns(4)
    cols[0].metric(
        "Latest sample close" if dataset["is_synthetic"] else "Last supplied close",
        number(last["close"]),
    )
    cols[1].metric("Observations", f"{len(candles):,}")
    cols[2].metric("Latest supplied volume", number(last["volume"], 0))
    cols[3].metric(
        "Evidence status", "Synthetic" if dataset["is_synthetic"] else "Historical import"
    )
    st.caption(
        f"Data window: {candles[0]['timestamp']} → {last['timestamp']} · "
        "Price currency and adjustment basis follow the source; values are not live quotes."
    )
    if st.button("Build evidence card", type="primary", width="content"):
        analysis = engine_request("analyze", candles)
        if analysis is not None:
            try:
                evidence = build_evidence(
                    candles,
                    analysis,
                    news=dataset.get("news", []),
                    symbol=dataset["symbol"],
                    fundamentals=dataset.get("fundamentals", {}),
                )
                st.session_state.analysis = analysis
                st.session_state.evidence = evidence
                st.session_state.pop("report", None)
                safe_storage(storage.save_evidence, evidence)
            except (RuntimeError, ValueError, TypeError) as exc:
                st.error(f"Evidence could not be assembled: {exc}")
    evidence = st.session_state.get("evidence")
    if evidence:
        render_evidence(evidence)
        st.download_button(
            "Download evidence JSON",
            json_download(evidence),
            file_name=f"{dataset['symbol']}_evidence.json",
            mime="application/json",
        )
    else:
        st.info(
            "Build a card to calculate price/volume evidence and make missing information explicit."
        )
    st.divider()
    st.markdown("### Analyst discussion")
    st.caption(
        "News analyst → technical analyst → reviewer. Their claims must refer to the same evidence record."
    )
    if st.button("Generate analyst report", disabled=not bool(evidence)):
        try:
            with st.spinner("Preparing the analyst report…"):
                report = generate_report(evidence, provider=provider, model=model)
            st.session_state.report = report
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    if st.session_state.get("report"):
        render_report(st.session_state.report)
        st.download_button(
            "Download analyst report",
            json_download(st.session_state.report),
            file_name=f"{dataset['symbol']}_report.json",
            mime="application/json",
        )
    with st.expander("Company fundamentals and publication dates"):
        fundamentals = dataset.get("fundamentals")
        if fundamentals:
            st.warning(
                "Illustrative company information only."
                if dataset["is_synthetic"]
                else "Use publication dates when assessing historical decisions."
            )
            st.json(fundamentals, expanded=False)
        else:
            st.info(
                "No verified fundamentals are attached to this historical file. The report must retain this gap."
            )
    with st.expander("News and company-event evidence"):
        news = dataset.get("news", [])
        if dataset["is_synthetic"]:
            st.caption(
                "The following event fixtures are fictional and contain no real news claims."
            )
        if news:
            st.dataframe(pd.DataFrame(news), hide_index=True, width="stretch")
        else:
            st.caption(
                "No dated news supplied; the system cannot infer historical news from candles."
            )


def price_liquidity(dataset: dict) -> None:
    st.markdown("### Price structure, volume and visible liquidity")
    st.caption(
        "Prior ranges, gaps and relative volume lead the analysis. Moving averages and RSI are supporting context."
    )
    analysis = st.session_state.get("analysis")
    overlay = st.multiselect(
        "Supporting overlays",
        ["sma20", "ema20"],
        format_func=lambda text: text.upper(),
        disabled=not bool(analysis),
    )
    st.plotly_chart(price_chart(dataset["candles"], analysis, overlay), width="stretch")
    if analysis:
        summary = analysis.get("summary", {})
        cols = st.columns(4)
        cols[0].metric("Relative volume", number(summary.get("relative_volume")) + "×")
        cols[1].metric("Prior range high", number(summary.get("prior_high")))
        cols[2].metric("Prior range low", number(summary.get("prior_low")))
        cols[3].metric("One-observation return", percent(summary.get("return_1d")))
        with st.expander("Supporting indicator values"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "SMA 20": summary.get("sma20"),
                            "EMA 20": summary.get("ema20"),
                            "RSI 14": summary.get("rsi14"),
                            "ATR 14": summary.get("atr14"),
                        }
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    else:
        st.caption(
            "Build the evidence card in Overview to add engine-calculated structure and indicators."
        )
    st.divider()
    indicator_lab(dataset)
    st.divider()
    st.markdown("### Order-book snapshot lab")
    depth = dataset.get("depth", {})
    if not depth.get("bids") or not depth.get("asks"):
        st.info(
            "This dataset has no order-book observations. OHLCV cannot recover depth, individual orders or true CVD."
        )
    else:
        if dataset["is_synthetic"]:
            st.warning(
                "SYNTHETIC DEPTH SNAPSHOT · No live feed, executions, cancellations or queue positions are represented."
            )
        else:
            st.info(
                f"UPLOADED SNAPSHOT · {depth.get('as_of')} · Source: {depth.get('source')}. "
                "User-provided depth is not independently verified and is separate from daily price history."
            )
        st.plotly_chart(depth_chart(depth["bids"], depth["asks"]), width="stretch")
        if st.button("Inspect displayed-depth balance"):
            result = engine_request("depth", depth["bids"], depth["asks"])
            if result is not None:
                st.session_state.depth_result = result
        result = st.session_state.get("depth_result")
        if result:
            cols = st.columns(3)
            cols[0].metric("Displayed spread", number(result.get("spread"), 4))
            cols[1].metric("Spread (bps)", number(result.get("spread_bps")))
            cols[2].metric("Visible-depth imbalance", number(result.get("depth_imbalance"), 3))
            show_items(result.get("assumptions"))
    st.caption(
        "Displayed book imbalance is a short-horizon liquidity observation. It does not establish "
        "executed buying/selling pressure or a long-term investment thesis."
    )
    with st.expander("Inspect supplied OHLCV observations"):
        st.dataframe(candle_frame(dataset["candles"]), hide_index=True, width="stretch")


def backtest_lab(dataset: dict) -> None:
    st.markdown("### Backtest lab")
    st.write(
        "Compare a price/volume rule, a simple indicator baseline and buy-and-hold on the same observations."
    )
    st.warning(
        "Synthetic experiment only: returns below cannot establish an investment strategy's effectiveness."
        if dataset["is_synthetic"]
        else "Historical results depend on source quality, corporate actions, universe selection and execution assumptions."
    )
    if len({row["timestamp"][:10] for row in dataset["candles"]}) != len(dataset["candles"]):
        st.warning(
            "This lab currently assumes daily bars for annualized statistics. Import one completed bar per trading date."
        )
        return
    with st.form("backtest_form"):
        a, b, c = st.columns(3)
        capital = a.number_input("Starting capital", min_value=1000.0, value=100000.0, step=10000.0)
        lookback = b.number_input("Price structure lookback", min_value=2, max_value=200, value=20)
        volume = c.number_input(
            "Relative-volume threshold", min_value=0.1, max_value=10.0, value=1.2, step=0.1
        )
        a, b, c = st.columns(3)
        commission = a.number_input(
            "Commission / charges per side (bps)", min_value=0.0, max_value=500.0, value=10.0
        )
        slippage = b.number_input(
            "Slippage per side (bps)", min_value=0.0, max_value=500.0, value=5.0
        )
        stop = c.number_input("Stop-loss distance (%)", min_value=1.0, max_value=99.0, value=8.0)
        exposure = st.slider("Capital exposure cap at entry (%)", 10, 100, 100, step=5)
        st.caption(
            "Cost inputs are simplified research assumptions, not an Indian broker's tax or fee schedule. "
            "A stop price is not a guaranteed execution price."
        )
        run = st.form_submit_button("Run the three-strategy comparison", type="primary")
    if run:
        options = dict(
            initial_capital=capital,
            lookback=int(lookback),
            volume_threshold=volume,
            commission_bps=commission,
            slippage_bps=slippage,
            stop_loss_pct=stop / 100,
            max_exposure=exposure / 100,
        )
        results = {}
        for label, strategy in STRATEGIES.items():
            result = engine_request("backtest", dataset["candles"], strategy=strategy, **options)
            if result is None:
                break
            results[label] = result
        if len(results) == len(STRATEGIES):
            st.session_state.backtests = results
            st.session_state.experiment_settings = options
    results = st.session_state.get("backtests")
    if not results:
        st.info(
            "Submit the form to create a reproducible comparison. No strategy has been run yet."
        )
        return
    st.caption("Showing the last submitted experiment. Change settings and run again to update it.")
    rows = []
    for label, result in results.items():
        metric = result.get("metrics", {})
        rows.append(
            {
                "Strategy": label,
                "Total return": percent(metric.get("total_return")),
                "Max drawdown": percent(metric.get("max_drawdown")),
                "Annualized volatility": percent(metric.get("annualized_volatility")),
                "Sharpe (assumptions apply)": number(metric.get("sharpe")),
                "Trade count": metric.get("trade_count"),
                "Turnover": number(metric.get("turnover")),
                "Exposure": percent(metric.get("exposure")),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    equity, drawdown = equity_charts(results)
    st.plotly_chart(equity, width="stretch")
    st.plotly_chart(drawdown, width="stretch")
    selected = st.selectbox("Inspect strategy trades", list(results))
    trades = results[selected].get("trades", [])
    if trades:
        st.dataframe(pd.DataFrame(trades), hide_index=True, width="stretch")
    else:
        st.caption("No executed trades for this run.")
    with st.expander("Execution assumptions and exact configuration"):
        st.json(st.session_state.get("experiment_settings", {}), expanded=False)
        show_items(results[selected].get("assumptions"))
    export = {
        "symbol": dataset["symbol"],
        "is_synthetic": dataset["is_synthetic"],
        "data_fingerprint": st.session_state.dataset_fingerprint,
        "settings": st.session_state.get("experiment_settings", {}),
        "results": results,
    }
    st.download_button(
        "Download backtest records",
        json_download(export),
        file_name=f"{dataset['symbol']}_backtests.json",
        mime="application/json",
    )


def monte_carlo_lab(dataset: dict) -> None:
    st.markdown("### Monte Carlo scenario lab")
    st.info(
        "Conditional scenarios, not price forecasts. Change assumptions to explore the sensitivity of possible outcomes."
    )
    if len({row["timestamp"][:10] for row in dataset["candles"]}) != len(dataset["candles"]):
        st.warning(
            "Daily calibration requires one completed bar per trading date. Intraday scenario calibration is a later extension."
        )
        return
    with st.form("simulation_form"):
        a, b, c = st.columns(3)
        method_label = a.selectbox(
            "Simulation model", ["Historical block bootstrap", "Geometric Brownian motion"]
        )
        horizon = b.number_input("Horizon (observations)", min_value=2, max_value=504, value=60)
        paths = c.selectbox("Simulation paths", [500, 1000, 5000], index=1)
        a, b, c = st.columns(3)
        capital = a.number_input(
            "Initial investment", min_value=1000.0, value=100000.0, step=10000.0
        )
        block = b.number_input("Bootstrap block size", min_value=1, max_value=60, value=5)
        seed = c.number_input("Random seed", min_value=0, max_value=2147483647, value=42)
        with st.expander("Stress assumptions"):
            a, b = st.columns(2)
            vol = a.slider("Volatility multiplier", 0.25, 3.0, 1.0, step=0.25)
            drift = b.slider("Annual drift adjustment (percentage points)", -50, 50, 0, step=5)
            a, b = st.columns(2)
            shock = a.slider("Immediate adverse shock (%)", -50, 0, 0, step=1)
            spread = b.number_input(
                "Execution spread / friction (bps)", min_value=0.0, max_value=500.0, value=0.0
            )
        st.caption(
            "Daily observations are assumed when annualizing parameters. Avoid mixing intraday bars "
            "into this daily research model. A bootstrap only samples information present in its history."
        )
        run = st.form_submit_button("Simulate scenarios", type="primary")
    if run:
        result = engine_request(
            "simulate",
            dataset["candles"],
            method="bootstrap" if method_label.startswith("Historical") else "gbm",
            paths=int(paths),
            horizon=int(horizon),
            seed=int(seed),
            capital=capital,
            block_size=int(block),
            volatility_multiplier=vol,
            annual_drift_shift=drift / 100,
            initial_shock_pct=shock / 100,
            execution_spread_bps=spread,
        )
        if result is not None:
            st.session_state.simulation = result
    result = st.session_state.get("simulation")
    if not result:
        st.caption("No simulation has been run for the current dataset.")
        return
    st.caption(
        "Last submitted simulation. Percentiles summarize this model and these assumptions only."
    )
    summary = result.get("summary", {})
    cols = st.columns(4)
    cols[0].metric("5th-percentile terminal value", number(summary.get("p05")))
    cols[1].metric("Median terminal value", number(summary.get("p50")))
    cols[2].metric("95th-percentile terminal value", number(summary.get("p95")))
    cols[3].metric("Simulated probability of loss", percent(summary.get("probability_loss")))
    st.plotly_chart(simulation_chart(result), width="stretch")
    cols = st.columns(3)
    cols[0].metric("95% value at risk (loss amount)", number(summary.get("var95")))
    cols[1].metric("95% expected shortfall", number(summary.get("expected_shortfall95")))
    cols[2].metric("95th-percentile max drawdown", percent(summary.get("max_drawdown_p95")))
    with st.expander("Calibration, model limits and reproducibility"):
        show_items(result.get("assumptions"))
        st.json(
            {
                key: value
                for key, value in result.items()
                if key not in {"sample_paths", "percentiles"}
            },
            expanded=False,
        )
    export = {
        "symbol": dataset["symbol"],
        "is_synthetic": dataset["is_synthetic"],
        "data_fingerprint": st.session_state.dataset_fingerprint,
        "result": result,
    }
    st.download_button(
        "Download simulation records",
        json_download(export),
        file_name=f"{dataset['symbol']}_scenarios.json",
        mime="application/json",
    )


def chatbot(dataset: dict, provider: str, model: str | None) -> None:
    st.markdown("### Ask about the evidence")
    st.write(
        "Explain a concept, inspect an alert, question a backtest assumption or compare scenario outcomes."
    )
    st.caption(
        "Examples: Why is visible imbalance different from CVD? What invalidates this evidence card? "
        "How does slippage affect the last experiment?"
    )
    st.caption(
        f"Current provider: {provider}. Context is the selected dataset and the experiments you have actually run."
    )
    history = st.session_state.setdefault("chat_history", [])
    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("citations"):
                with st.expander("Evidence references"):
                    show_items(message["citations"])
    question = st.chat_input("Ask a finance or research question")
    if question:
        backtests = st.session_state.get("backtests", {})
        simulation = st.session_state.get("simulation", {})
        report = st.session_state.get("report", {})
        context = {
            "symbol": dataset["symbol"],
            "is_synthetic": dataset["is_synthetic"],
            "data_description": dataset["description"],
            "evidence": st.session_state.get("evidence", {}),
            "analysis": st.session_state.get("analysis", {}).get("summary", {}),
            "backtests": {
                name: {"metrics": run.get("metrics", {}), "assumptions": run.get("assumptions", [])}
                for name, run in backtests.items()
            },
            "backtest": {
                "metrics": {name: run.get("metrics", {}) for name, run in backtests.items()}
            },
            "simulation": {
                key: value
                for key, value in simulation.items()
                if key not in {"sample_paths", "percentiles"}
            },
            "report": {
                key: report[key] for key in ("news", "market", "reviewer", "mode") if key in report
            },
        }
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        try:
            with st.spinner("Reviewing the available evidence…"):
                response = answer_question(question, context, provider=provider, model=model)
            answer = str(response.get("answer", "No answer was returned."))
            citations = response.get("citations", [])
            history.append({"role": "assistant", "content": answer, "citations": citations})
            with st.chat_message("assistant"):
                st.write(answer)
                if citations:
                    with st.expander("Evidence references"):
                        show_items(citations)
        except (RuntimeError, ValueError) as exc:
            history.append({"role": "assistant", "content": f"Request was not completed: {exc}"})
            st.error(str(exc))
    if history and st.button("Clear this conversation"):
        st.session_state.chat_history = []
        st.rerun()


def monitoring() -> None:
    st.markdown("### Monitoring centre")
    st.write(
        "The background worker and dashboard are separate processes. Monitoring runs only while its host is awake, "
        "connected and the worker is running. Demo mode replays fixtures. Optional Upstox mode polls read-only snapshots "
        "using your own permitted account access; it is not a full order-event stream."
    )
    heartbeat = safe_storage(storage.get_heartbeat)
    if heartbeat:
        st.info(
            f"Last recorded worker heartbeat (UTC): {heartbeat.get('updated_at', 'unavailable')}"
        )
        payload = heartbeat.get("payload", {})
        st.caption(
            f"Recorded worker state: {plain_text(payload)}. A recorded heartbeat alone does not prove it is running now."
        )
    else:
        st.warning("No worker heartbeat recorded. No continuous monitoring is confirmed.")
    existing = safe_storage(storage.get_watchlist, default=[]) or []
    mode = st.radio(
        "Watchlist configuration",
        ["Synthetic replay", "Upstox read-only snapshots"],
        horizontal=True,
    )
    if mode == "Synthetic replay":
        with st.form("watchlist_form"):
            watchlist = st.multiselect(
                "Synthetic instruments to monitor",
                SYMBOLS,
                default=[symbol for symbol in existing if symbol in SYMBOLS],
            )
            if st.form_submit_button("Save demo watchlist"):
                safe_storage(storage.set_watchlist, watchlist)
                st.success(
                    "Watchlist saved. Start the worker in demo mode to replay these fixtures."
                )
    else:
        mapping = safe_storage(storage.get_setting, "upstox_instruments", default={}) or {}
        with st.form("live_watchlist_form"):
            mappings = st.text_area(
                "Indian cash-equity mappings (one EXCHANGE:SYMBOL=instrument-key per line)",
                value="\n".join(f"{symbol}={key}" for symbol, key in mapping.items()),
                placeholder="Use verified instrument keys from your provider's instrument catalogue.",
            )
            st.caption(
                "Use verified provider identifiers; the app does not guess security IDs. "
                "Saving replaces the worker watchlist. Match the worker's --mode to that watchlist."
            )
            if st.form_submit_button("Save live snapshot watchlist"):
                try:
                    parsed = {}
                    for line in mappings.splitlines():
                        if not line.strip():
                            continue
                        symbol, key = [part.strip() for part in line.split("=", 1)]
                        if not symbol or not re.fullmatch(r"(?:NSE_EQ|BSE_EQ)\|[A-Za-z0-9]+", key):
                            raise ValueError(
                                "Each entry needs a symbol and a verified NSE_EQ or BSE_EQ cash-equity key."
                            )
                        parsed[symbol.upper()] = key
                    if not parsed:
                        raise ValueError("Add at least one instrument mapping.")
                    safe_storage(storage.set_setting, "upstox_instruments", parsed)
                    safe_storage(storage.set_watchlist, list(parsed))
                    st.success(
                        "Live mapping saved. Quotes are retrieved only on an explicit poll or by your worker."
                    )
                except ValueError as exc:
                    st.error(str(exc))
        configured = bool(os.getenv("UPSTOX_ACCESS_TOKEN"))
        st.caption(
            "UPSTOX_ACCESS_TOKEN configured locally."
            if configured
            else "Set UPSTOX_ACCESS_TOKEN in the local environment to enable permitted snapshots."
        )
        if st.button("Poll the saved live watchlist once", disabled=not configured):
            try:
                with st.spinner("Fetching read-only quote snapshots…"):
                    response = run_once(mode="live")
                st.session_state.live_poll = response
            except (RuntimeError, ValueError, OSError, sqlite3.Error) as exc:
                st.error(str(exc))
        if st.session_state.get("live_poll"):
            response = st.session_state.live_poll
            if response.get("errors"):
                show_items(response["errors"])
            observations = response.get("observations", [])
            if observations:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Symbol": row.get("symbol"),
                                "As of": row.get("as_of"),
                                "Last supplied price": row.get("last_price"),
                                "Freshness": row.get("freshness"),
                                "Age (seconds)": row.get("age_seconds"),
                                "Source": row.get("source"),
                            }
                            for row in observations
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
                with st.expander("Snapshot details and source limitations"):
                    st.json(observations, expanded=False)
        st.caption(
            "Snapshots are kept separate from the synthetic or imported research dataset. "
            "Stale quotes and closed-market observations are recorded as data gaps, not fresh alerts."
        )
    if st.button("Refresh worker records"):
        st.rerun()
    events = safe_storage(storage.list_events, limit=50, default=[]) or []
    st.markdown("#### Recent recorded events")
    if events:
        rows = [
            {
                "Recorded UTC": item.get("created_at"),
                "Symbol": item.get("symbol"),
                "Kind": item.get("kind"),
                "Event": plain_text(item.get("payload", {})),
            }
            for item in events
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        with st.expander("Complete event records"):
            st.json(events, expanded=False)
    else:
        st.caption(
            "No recorded events. The dashboard does not invent activity or start a worker automatically."
        )
    with st.expander("Run the worker from a separate terminal"):
        st.caption("From the project folder with the Python environment activated:")
        st.code(
            "python -m app.monitor --mode demo --once\npython -m app.monitor --mode demo --interval 60\n"
            "python -m app.monitor --mode live --interval 60",
            language="powershell",
        )
        st.caption(
            "Use --help for supported options. Stop the process with Ctrl+C. "
            "Intervals replay fixtures; they do not convert them into live observations."
        )


def settings(provider: str, model: str | None) -> None:
    st.markdown("### Connections and project boundaries")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Component": "Numerical research",
                    "State": "C++ executable; compiled locally",
                    "Use": "Indicators, tests, depth and simulation",
                },
                {
                    "Component": "Rules assistant",
                    "State": "Available without a model",
                    "Use": "Deterministic evidence explanations",
                },
                {
                    "Component": "OpenRouter",
                    "State": "Key configured"
                    if os.getenv("OPENROUTER_API_KEY")
                    else "Not configured",
                    "Use": "Explicit free-only AI requests",
                },
                {
                    "Component": "Ollama",
                    "State": "Availability checked on request",
                    "Use": "Optional local inference",
                },
                {
                    "Component": "Upstox snapshot access",
                    "State": "Token configured; verify by polling"
                    if os.getenv("UPSTOX_ACCESS_TOKEN")
                    else "Not configured",
                    "Use": "Optional permitted read-only quotes; no full order-event feed",
                },
                {
                    "Component": "US cash equities",
                    "State": "Later extension",
                    "Use": "Same engine with market-specific data and costs",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.write(f"Selected assistant: **{provider}**" + (f" · Model: `{model}`" if model else ""))
    st.caption(
        "API credentials are read from the local environment. They are not requested in chat, written to source "
        "or displayed here. No paid model fallback is permitted."
    )
    with st.expander("Configure OpenRouter in your local PowerShell terminal"):
        st.code(
            '$env:OPENROUTER_API_KEY = "your-own-key"\n'
            '$env:OPENROUTER_MODEL = "openrouter/free"\n'
            "python -m streamlit run app/dashboard.py",
            language="powershell",
        )
        st.caption(
            "Replace the placeholder locally. Restart Streamlit after changing its environment. "
            "Free-provider availability and upstream quotas may change; local budget checks also apply."
        )
    with st.expander("Configure the local model"):
        st.code(
            'ollama pull qwen3:4b\n$env:OLLAMA_MODEL = "qwen3:4b"\n'
            "python -m streamlit run app/dashboard.py",
            language="powershell",
        )
        st.caption(
            "The installed model must fit your current laptop. The numerical engine does not require a GPU."
        )
    st.markdown("#### What this version can substantiate")
    show_items(
        [
            "A reproducible C++ research workflow on synthetic fixtures or user-supplied historical OHLCV.",
            "Numerical strategy comparisons with explicit cost and execution assumptions.",
            "Conditional simulations, evidence gaps and separately inspectable agent reports.",
            "Persistent event recording and a synthetic replay worker.",
        ]
    )
    st.caption(
        "Live broker access, authentic order-flow history, fundamentals/news connectors and measured strategy "
        "effectiveness require separate data and validation. Current functionality does not send trades."
    )


def main() -> None:
    dataset = select_dataset()
    provider, model = model_controls()
    st.title("Equity Research Workstation")
    st.caption("PRICE + EVENTS + LIQUIDITY · EXPLAINABLE RESEARCH · REPRODUCIBLE EXPERIMENTS")
    if dataset["is_synthetic"]:
        st.warning(
            f"SYNTHETIC DEMO · {dataset['symbol']} · Fictional prices, company data, events and order book. "
            "Use this to inspect the software, never as investment evidence."
        )
    else:
        st.info(
            f"HISTORICAL CSV · {dataset['symbol']} · User-supplied data, freshness and adjustment basis unverified. "
            "Optional attached evidence remains user-supplied; no continuous live feed is implied."
        )
    tabs = st.tabs(
        [
            "Overview & evidence",
            "Price & liquidity",
            "Backtest",
            "Monte Carlo",
            "Research chat",
            "Monitoring",
            "Stock catalogue",
            "Settings",
        ]
    )
    with tabs[0]:
        overview(dataset, provider, model)
    with tabs[1]:
        price_liquidity(dataset)
    with tabs[2]:
        backtest_lab(dataset)
    with tabs[3]:
        monte_carlo_lab(dataset)
    with tabs[4]:
        chatbot(dataset, provider, model)
    with tabs[5]:
        monitoring()
    with tabs[6]:
        stock_catalogue()
    with tabs[7]:
        settings(provider, model)
    st.divider()
    st.caption(
        "Student research prototype · India first · Cash equities only · "
        "Every result depends on its inputs, time horizon and stated assumptions."
    )


if __name__ == "__main__":
    main()
