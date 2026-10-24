"""Python workstation UI for the independently compiled C++ research engine.

Start from the repository root: python -m streamlit run app/dashboard.py
Every expensive engine or model operation requires an explicit user action.
"""

# ruff: noqa: E402 -- Streamlit runs a file path; establish the project import root first.

from __future__ import annotations

import hashlib
from datetime import date, time
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

from app import history, storage
from app.attachments import load_evidence_json
from app.accounting import load_actions, market_options
from app.assessment import STRATEGIES
from app.chat import answer_question
from app.demo import SYMBOLS, load_demo, load_accounting_demo
from app.experiment_ui import (
    accounting_view,
    cost_controls,
    cost_model_selector,
    data_readiness,
    validation_lab,
)
from app.engine_bridge import (
    EngineClient,
    EngineUnavailable,
    load_candles_csv,
    validate_daily_candles,
)
from app.monitor import run_once
from app.stock_workspace import stock_workspace
from app.strategy_risk import strategy_risk
from app.recommendations import stock_ideas, strategy_guide
from app.research_labs import indicator_lab, stock_catalogue
from app.services import build_evidence, generate_report
from app.ui_helpers import (
    candle_frame,
    equity_charts,
    json_download,
    number,
    percent,
    plain_text,
    price_chart,
    render_evidence,
    render_report,
    render_assessment,
    show_items,
    simulation_chart,
    terminal_distribution,
    trade_chart,
)
from app.workspace import (
    go_page,
    safe_storage,
    saved_research,
    sidebar_navigation,
    sidebar_workspace,
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
    "chat_history",
    "experiment_settings",
    "indicator_result",
    "indicator_settings",
    "idea_cards",
    "validation_study",
    "strategy_simulation",
)


def engine_request(operation: str, *args, **kwargs) -> dict | None:
    try:
        with st.spinner("Running the C++ engine…"):
            return getattr(EngineClient(), operation)(*args, **kwargs)
    except EngineUnavailable as exc:
        st.error(str(exc))
        st.caption("Compile the engine with the setup instructions in README.md, then retry.")
        return None
    except (RuntimeError, ValueError, OSError) as exc:
        st.error(str(exc))
        return None


def model_controls() -> tuple[str, str | None]:
    with st.sidebar.expander("Assistant settings", expanded=False):
        label = st.selectbox(
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
            model = st.text_input(
                "Free model ID",
                value=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
                help="Only the free router or a currently verified :free model is allowed.",
            )
            st.caption(
                "Key configured"
                if os.getenv("OPENROUTER_API_KEY")
                else "Set OPENROUTER_API_KEY locally before making a request."
            )
            usage = safe_storage(storage.usage_summary, default={}) or {}
            if usage:
                st.caption(
                    f"Local daily budget: {usage.get('used', 0)} used / "
                    f"{usage.get('daily_limit', '?')} limit"
                )
        elif provider == "ollama":
            model = st.text_input(
                "Installed model name", value=os.getenv("OLLAMA_MODEL", "qwen3:4b")
            )
            st.caption("Requires a running local Ollama server; GPU optional.")
        else:
            st.caption("Deterministic explanations work offline. Generative AI is optional.")
        st.caption("Models run only when you request a report or send a question.")
        return provider, model


def select_dataset() -> dict | None:
    with st.sidebar.expander("Research data", expanded=True):
        source = st.radio(
            "Data source",
            (
                ["Synthetic demo", "Accounting example"]
                if os.getenv("STOCK_RESEARCH_TEST_FIXTURES") == "1"
                else []
            )
            + ["Historical library", "Upload historical CSV"],
            key="data_source",
        )
        if source == "Historical library":
            ready = history.ready_stocks()
            if not ready:
                st.info(
                    "Prepare the real history library once using scripts/prepare_history.py. No broker key is needed."
                )
            else:
                imported = st.session_state.pop("new_history_stock", None)
                if imported in ready:
                    st.session_state.historical_stock = imported
                symbol = st.selectbox(
                    "Historical stock",
                    ready,
                    index=ready.index("INFY") if "INFY" in ready else 0,
                    key="historical_stock",
                )
                try:
                    dataset = history.load_stock(symbol)
                except (OSError, ValueError, KeyError) as exc:
                    st.error(str(exc))
                    return None
                bounds = (
                    date.fromisoformat(dataset["candles"][0]["timestamp"]),
                    date.fromisoformat(dataset["candles"][-1]["timestamp"]),
                )
                period = st.date_input(
                    "Research window",
                    value=bounds,
                    min_value=bounds[0],
                    max_value=bounds[1],
                    key="period_" + symbol,
                )
                if len(period) != 2:
                    st.info("Choose both dates to open the research window.")
                    return None
                dataset["candles"] = [
                    c
                    for c in dataset["candles"]
                    if period[0].isoformat() <= c["timestamp"] <= period[1].isoformat()
                ]
                if len(dataset["candles"]) < 30:
                    st.info("Choose at least 30 daily observations.")
                    return None
                dataset["decision_time"] = dataset["candles"][-1]["timestamp"] + "T15:30:00+05:30"
                st.caption("Real daily history · hard cutoff 31 Dec 2020 · no live prices")
            with st.expander("Add another historical stock"):
                listing = history.catalogue()
                st.caption(
                    f"{len(ready)} stocks ready locally · {len(listing['stocks'])} source files discoverable. Pre-2021 coverage is checked when imported."
                )
                query = (
                    st.text_input("Find historical NSE symbol", placeholder="e.g. ASIANPAINT")
                    .strip()
                    .upper()
                )
                matches = [
                    s["symbol"] for s in listing["stocks"] if query and query in s["symbol"]
                ][:100]
                selected = st.selectbox("Matching historical symbol", matches) if matches else None
                if st.button("Download selected history", disabled=selected is None):
                    try:
                        with st.spinner("Downloading and validating the historical file…"):
                            history.fetch_stock(selected)
                        st.session_state.new_history_stock = selected
                        st.rerun()
                    except (RuntimeError, ValueError, OSError) as exc:
                        st.error(str(exc))
            if not ready:
                return None
        elif source == "Synthetic demo":
            symbol = st.selectbox(
                "Demonstration instrument",
                SYMBOLS,
                key="demo_symbol",
                format_func=lambda value: value.replace("DEMO_", "").title(),
            )
            dataset = load_demo(symbol)
            dataset["bar_interval"] = "1d"
            dataset["decision_time"] = dataset["candles"][-1]["timestamp"] + "T15:30:00+05:30"
        elif source == "Accounting example":
            dataset = load_accounting_demo()
            st.caption(dataset["description"])
        else:
            symbol = st.text_input("Instrument label", value="MY_NSE_STOCK").strip().upper()
            uploaded = st.file_uploader("Historical OHLCV CSV", type=["csv"])
            st.caption(
                "Required: Date/Timestamp, Open, High, Low, Close, Volume. "
                "Use consistent, documented corporate-action adjustments."
            )
            if uploaded is None:
                st.caption("Choose a file to enable research on imported prices.")
                return None
            try:
                candles = load_candles_csv(uploaded.getvalue())
                if os.getenv("STOCK_RESEARCH_TEST_FIXTURES") != "1":
                    excluded = sum(c["timestamp"][:10] > history.CUTOFF for c in candles)
                    candles = [c for c in candles if c["timestamp"][:10] <= history.CUTOFF]
                    if len(candles) < 30:
                        raise ValueError(
                            "The research edition requires at least 30 daily bars through 31 Dec 2020."
                        )
                    if excluded:
                        st.caption(
                            f"Excluded {excluded} rows after the 31 Dec 2020 research cutoff."
                        )
            except (ValueError, RuntimeError, OSError) as exc:
                st.error(f"CSV validation failed: {exc}")
                return None
            dataset = {
                "symbol": symbol or "UPLOADED_STOCK",
                "candles": candles,
                "news": [],
                "fundamentals": {},
                "depth": {},
                "is_synthetic": st.checkbox("This file contains fictional / test prices"),
                "bar_interval": "1d"
                if st.checkbox("I confirm these are completed daily bars")
                else "unconfirmed",
                "description": f"User-supplied historical file: {uploaded.name}",
                "price_basis": {
                    "Unverified": "unverified",
                    "Raw / unadjusted": "raw",
                    "Already adjusted": "adjusted",
                }[
                    st.selectbox(
                        "Price basis", ["Unverified", "Raw / unadjusted", "Already adjusted"]
                    )
                ],
                "corporate_actions": [],
            }
            if len(candles[-1]["timestamp"]) == 10:
                close_time = st.time_input("Daily decision time (India time)", value=time(15, 30))
                dataset["decision_time"] = (
                    candles[-1]["timestamp"] + "T" + close_time.isoformat() + "+05:30"
                )
                st.caption(
                    "Confirm the decision time against your source. Special sessions and market holidays are not verified automatically."
                )
            attachment = st.file_uploader(
                "Optional dated evidence JSON", type=["json"], key="evidence_attachment"
            )
            st.caption(
                "Attach sourced news or published company figures. See README for the format."
            )
            if attachment is not None:
                try:
                    dataset.update(load_evidence_json(attachment.getvalue()))
                except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                    st.error(f"Evidence attachment rejected: {exc}")
                    return None
            actions_file = st.file_uploader(
                "Optional corporate actions JSON", type=["json"], key="actions_attachment"
            )
            if actions_file is not None:
                try:
                    if dataset["corporate_actions"]:
                        raise ValueError(
                            "Provide actions in one attachment only; do not apply them twice."
                        )
                    dataset["corporate_actions"] = load_actions(actions_file.getvalue())
                except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                    st.error(f"Corporate action file rejected: {exc}")
                    return None
            st.caption(
                "Action files require raw prices, source, announcement/ex-dates and dividend pay dates. Adjusted data must not also receive actions."
            )
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "symbol": dataset["symbol"],
                    "candles": dataset["candles"],
                    "synthetic": dataset["is_synthetic"],
                    "news": dataset.get("news"),
                    "fundamentals": dataset.get("fundamentals"),
                    "bar_interval": dataset.get("bar_interval"),
                    "decision_time": dataset.get("decision_time"),
                    "price_basis": dataset.get("price_basis"),
                    "corporate_actions": dataset.get("corporate_actions"),
                    "history_quality": dataset.get("history_quality"),
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
    change = float(last["close"]) / float(candles[-2]["close"]) - 1
    with st.container(horizontal=True, gap="small"):
        st.metric(
            "Sample close" if dataset["is_synthetic"] else "Historical close",
            number(last["close"]),
            delta=percent(change) + " vs prior bar",
            border=True,
            width="stretch",
        )
        st.metric("Price bars", f"{len(candles):,}", border=True, width="stretch")
        volume = last["volume"]
        st.metric(
            "Latest volume",
            f"{volume / 1_000_000:.2f}M" if volume >= 1_000_000 else number(volume, 0),
            border=True,
            width="stretch",
        )
        st.metric(
            "Evidence facts",
            len(st.session_state.get("evidence", {}).get("facts", [])),
            border=True,
            width="stretch",
            help="Build a research brief below to assemble dated facts.",
        )
    data_readiness(dataset)
    if st.button("Assess selected stock", type="primary", icon=":material/analytics:"):
        analysis = engine_request("analyze", candles, **market_options(dataset))
        if analysis:
            record_analysis(dataset, analysis)
            st.rerun()
    evidence = st.session_state.get("evidence")
    if evidence:
        case = evidence.get("assessment", {})
        with st.expander(
            f"Stock recommendation · {case.get('stance', 'Unassessed')} · Bull {number(case.get('bullish'), 0)} / Bear {number(case.get('bearish'), 0)}",
            expanded=True,
        ):
            render_assessment(evidence)
    chart_column, desk_column = st.columns([2.4, 1], gap="medium")
    with chart_column, st.container(border=True):
        st.caption("MARKET CONTEXT")
        st.markdown("### Price & participation")
        period = st.radio(
            "Chart range",
            ["1M", "3M", "6M", "All"],
            index=2,
            horizontal=True,
            label_visibility="collapsed",
        )
        count = {"1M": 21, "3M": 63, "6M": 126, "All": len(candles)}[period]
        visible = candles[-count:]
        st.plotly_chart(price_chart(visible), width="stretch", config={"displayModeBar": False})
        st.caption(
            f"{visible[0]['timestamp']} — {visible[-1]['timestamp']} · {len(visible)} supplied bars · Not live"
        )
    with desk_column:
        with st.container(border=True):
            st.caption("RESEARCH DESK")
            st.markdown("### Your next move")
            st.caption("Explore the data, test an idea, then challenge the result.")
            for label, target, icon in [
                ("Explore market analysis", "Market analysis", "candlestick_chart"),
                ("Compare strategies", "Backtesting", "query_stats"),
                ("Challenge strategy robustness", "Validation", "fact_check"),
                ("Explore risk scenarios", "Monte Carlo", "ssid_chart"),
                ("Ask the assistant", "Assistant", "forum"),
            ]:
                st.button(
                    label,
                    icon=f":material/{icon}:",
                    width="stretch",
                    on_click=go_page,
                    args=(target,),
                )
        with st.container(border=True):
            st.caption("YOUR WORKSPACE")
            reports = safe_storage(storage.list_reports, limit=3, default=[]) or []
            st.markdown("**Recent research**")
            if reports:
                for report in reports:
                    st.caption(
                        f"{report['evidence']['symbol']} · {report['generated_at'][:10]} · {report['provider']}"
                    )
            else:
                st.caption("No reports saved yet. Build an evidence card below to begin.")
            st.button(
                "Open saved research",
                icon=":material/history:",
                width="stretch",
                on_click=go_page,
                args=("Saved research",),
            )
    st.caption(
        "Research prices and volume follow the supplied source. Demo events are fictional; no live connection is implied."
    )
    brief, sources = st.tabs(["Research brief", "News & company evidence"])
    with brief:
        research_brief(dataset, provider, model)
    with sources:
        company_evidence(dataset)


def record_analysis(dataset: dict, analysis: dict) -> None:
    evidence = build_evidence(
        dataset["candles"],
        analysis,
        news=dataset.get("news", []),
        symbol=dataset["symbol"],
        fundamentals=dataset.get("fundamentals", {}),
        is_synthetic=dataset["is_synthetic"],
        decision_time=dataset.get("decision_time"),
        bar_interval=dataset.get("bar_interval", "unconfirmed"),
    )
    st.session_state.analysis = analysis
    st.session_state.evidence = evidence
    if dataset.get("history_quality"):
        evidence["history_source"] = dataset["history_quality"]
    st.session_state.pop("report", None)
    safe_storage(storage.save_evidence, evidence)


def research_brief(dataset: dict, provider: str, model: str | None) -> None:
    candles = dataset["candles"]
    st.markdown("### Research brief")
    st.caption("Build an evidence card, then review a source-grounded analyst report.")
    if st.button("Build evidence card", type="primary", width="content"):
        analysis = engine_request("analyze", candles, **market_options(dataset))
        if analysis is not None:
            try:
                record_analysis(dataset, analysis)
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
        st.caption(
            "Your evidence card will appear here with supporting observations, gaps and invalidation conditions."
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


def company_evidence(dataset: dict) -> None:
    with st.expander("Company fundamentals and publication dates", expanded=True):
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
    with st.expander("News and company-event evidence", expanded=True):
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
    chart_tab, indicators_tab, data_tab = st.tabs(
        ["Price & volume", "Indicator lab", "Source data"]
    )
    with chart_tab:
        price_structure(dataset)
    with indicators_tab:
        indicator_lab(dataset)
    with data_tab:
        st.caption(
            "Supplied OHLCV observations · source quality and adjustment basis require review"
        )
        st.dataframe(candle_frame(dataset["candles"]), hide_index=True, width="stretch")
        company_evidence(dataset)


def price_structure(dataset: dict) -> None:
    st.markdown("### Price and volume")
    st.caption(
        "Prior ranges, gaps and relative volume lead the analysis. Moving averages and RSI are supporting context."
    )
    analysis = st.session_state.get("analysis")
    if not analysis and st.button("Calculate price structure", type="primary"):
        analysis = engine_request("analyze", dataset["candles"], **market_options(dataset))
        if analysis:
            record_analysis(dataset, analysis)
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
            "Calculate price structure above to add prior ranges, volume context and overlays."
        )


def daily_experiment_ready(dataset: dict) -> bool:
    try:
        validate_daily_candles(dataset["candles"], dataset.get("bar_interval", "unconfirmed"))
        return True
    except ValueError as exc:
        st.warning(str(exc))
        st.caption(
            "Open Research data in the sidebar to confirm the bar interval. Annualized results assume 252 daily observations per year."
        )
        return False


def backtest_lab(dataset: dict) -> None:
    st.markdown("### Backtest lab")
    st.write(
        "Compare a price/volume rule, a simple indicator baseline and buy-and-hold on the same observations."
    )
    st.caption(
        "Synthetic experiment only: returns below cannot establish an investment strategy's effectiveness."
        if dataset["is_synthetic"]
        else "Historical results depend on source quality, corporate actions, universe selection and execution assumptions."
    )
    if not daily_experiment_ready(dataset):
        return
    data_readiness(dataset)
    model = cost_model_selector("backtest_cost_model", dataset)
    with (
        st.expander(
            "Strategy & execution settings", expanded=not bool(st.session_state.get("backtests"))
        ),
        st.form("backtest_form"),
    ):
        selection = st.multiselect(
            "Strategies to compare", list(STRATEGIES), default=list(STRATEGIES)
        )
        evaluation = st.selectbox(
            "Evaluation window", ["Last 30% chronological holdout", "Full history (exploratory)"]
        )
        st.caption(
            "Holdout starts in cash; prior bars warm up features only. Rules are fixed hypotheses. Tuning after viewing the holdout invalidates its untouched status."
        )
        a, b, c = st.columns(3)
        capital = a.number_input("Starting capital", min_value=1000.0, value=100000.0, step=10000.0)
        lookback = b.number_input("Price structure lookback", min_value=2, max_value=200, value=20)
        volume = c.number_input(
            "Breakout relative-volume threshold", min_value=0.1, max_value=10.0, value=1.2, step=0.1
        )
        costs = cost_controls(model, "backtest")
        b, c = st.columns(2)
        slippage = b.number_input(
            "Slippage per side (bps)", min_value=0.0, max_value=500.0, value=5.0
        )
        stop = c.number_input("Stop-loss distance (%)", min_value=1.0, max_value=99.0, value=8.0)
        exposure = st.slider("Capital exposure cap at entry (%)", 10, 100, 100, step=5)
        st.caption(
            "A stop price is not a guaranteed execution price. Submitted costs and action inputs are retained in the export."
        )
        run = st.form_submit_button(
            "Run strategy comparison", type="primary", disabled=not selection
        )
    if run:
        st.session_state.pop("backtests", None)
        st.session_state.pop("experiment_settings", None)
        options = dict(
            initial_capital=capital,
            lookback=int(lookback),
            volume_threshold=volume,
            **costs,
            slippage_bps=slippage,
            stop_loss_pct=stop / 100,
            max_exposure=exposure / 100,
            evaluation_start=int(len(dataset["candles"]) * 0.7)
            if evaluation.startswith("Last")
            else 0,
            **market_options(dataset),
        )
        if len(dataset["candles"]) - options["evaluation_start"] < 2:
            st.warning(
                "The holdout needs at least two daily bars. Supply a longer history or choose Full history."
            )
            return
        results = {}
        for label in selection:
            strategy = STRATEGIES[label]
            result = engine_request("backtest", dataset["candles"], strategy=strategy, **options)
            if result is None:
                break
            results[label] = result
        if len(results) == len(selection):
            st.session_state.backtests = results
            st.session_state.experiment_settings = options
            st.rerun()
    results = st.session_state.get("backtests")
    if not results:
        st.info(
            "Submit the form to create a reproducible comparison. No strategy has been run yet."
        )
        return
    st.caption("Showing the last submitted experiment. Change settings and run again to update it.")
    with st.container(horizontal=True, gap="small"):
        for label, result in results.items():
            st.metric(
                label,
                percent(result.get("metrics", {}).get("total_return")),
                border=True,
                width="stretch",
                help="Total return under the submitted assumptions, not a live result.",
            )
    rows = []
    for label, result in results.items():
        metric = result.get("metrics", {})
        rows.append(
            {
                "Strategy": label,
                "Total return": percent(metric.get("total_return")),
                "CAGR (daily assumption)": percent(metric.get("cagr")),
                "Max drawdown": percent(metric.get("max_drawdown")),
                "Annualized volatility": percent(metric.get("annualized_volatility")),
                "Sharpe (assumptions apply)": number(metric.get("sharpe")),
                "Trade count": metric.get("trade_count"),
                "Turnover": number(metric.get("turnover")),
                "Time invested": percent(metric.get("exposure")),
                "Closed trades": metric.get("closed_trades"),
                "Win rate (closed trades)": percent(metric.get("win_rate")),
                "Profit factor": number(metric.get("profit_factor")),
                "Fees paid": number(metric.get("fees_paid")),
            }
        )
    performance, replay_tab, risk_tab, trades_tab = st.tabs(
        ["Performance", "Equity replay", "Monte Carlo risk", "Trades & accounting"]
    )
    with performance:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Net returns include submitted charges. Open positions remain marked to market.")
        st.button(
            "Challenge these rules in Validation",
            icon=":material/fact_check:",
            on_click=go_page,
            args=("Validation",),
        )
    with replay_tab:
        replay = st.toggle("Animated backtest replay", value=True)
        st.caption(
            "Play / Pause replays a completed run, with up to 300 displayed curve points. Metrics use every bar."
        )
        equity, drawdown = equity_charts(results, replay=replay)
        st.plotly_chart(equity, width="stretch")
        st.plotly_chart(drawdown, width="stretch")
    with trades_tab:
        selected = st.selectbox("Inspect strategy trades", list(results))
        evaluation = results[selected].get("evaluation", {})
        st.caption(
            f"{evaluation.get('start')} → {evaluation.get('end')} · {evaluation.get('bars')} evaluation bars"
        )
        accounting_view(results[selected])
        st.plotly_chart(trade_chart(dataset["candles"], results[selected]), width="stretch")
        trades = results[selected].get("trades", [])
        if trades:
            st.dataframe(pd.DataFrame(trades), hide_index=True, width="stretch")
        else:
            st.caption("No executed trades for this run.")
        with st.expander("Execution assumptions and exact configuration"):
            st.json(st.session_state.get("experiment_settings", {}), expanded=False)
            show_items(results[selected].get("assumptions"))
    with risk_tab:
        strategy_risk(dataset, results, st.session_state.get("experiment_settings", {}))
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
    with st.expander("Strategy rules, market fit and failure cases"):
        strategy_guide()


def monte_carlo_lab(dataset: dict) -> None:
    st.markdown("### Monte Carlo scenario lab")
    st.info(
        "Conditional scenarios, not price forecasts. Change assumptions to explore the sensitivity of possible outcomes."
    )
    st.caption(
        "This models a single invested wealth process from stock returns, not the selected backtest strategy or a diversified portfolio."
    )
    if not daily_experiment_ready(dataset):
        return
    with (
        st.expander("Scenario settings", expanded=not bool(st.session_state.get("simulation"))),
        st.form("simulation_form"),
    ):
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
            **market_options(dataset),
        )
        if result is not None:
            st.session_state.simulation = result
            st.rerun()
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
    replay = st.toggle("Animated scenario replay", value=True)
    st.caption(
        "Play / Pause reveals simulated paths through time. The band is a conditional percentile range, not a confidence interval for the real future; metrics describe the complete run."
    )
    st.plotly_chart(simulation_chart(result, replay=replay), width="stretch")
    with st.expander("Terminal outcome distribution", expanded=True):
        st.plotly_chart(terminal_distribution(result), width="stretch")
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
    with st.expander("How monitoring works"):
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
        (["Synthetic replay"] if os.getenv("STOCK_RESEARCH_TEST_FIXTURES") == "1" else [])
        + ["Upstox read-only snapshots"],
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
                    "Use": "Price/volume analysis, backtests and simulations",
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
            "A reproducible C++ research workflow on cached real histories or imported OHLCV through 2020.",
            "Numerical strategy comparisons with explicit cost and execution assumptions.",
            "Conditional simulations, evidence gaps and separately inspectable agent reports.",
            "Persistent event recording and a synthetic replay worker.",
        ]
    )
    st.caption(
        "Live broker access, authentic order-flow history, fundamentals/news connectors and measured strategy "
        "effectiveness require separate data and validation. Current functionality does not send trades."
    )


PAGES = {
    "Stock workspace": "One stock, one window, connected research and risk analysis.",
    "Overview": "A clear view of your research, evidence and next decisions.",
    "Market analysis": "Inspect price structure and volume, then add supporting indicators.",
    "Stock ideas": "Compare explainable bullish and bearish research cases from available histories.",
    "Backtesting": "Compare strategies under the same execution assumptions.",
    "Validation": "Challenge fixed rules across chronological periods and higher costs.",
    "Monte Carlo": "Explore a range of conditional outcomes.",
    "Assistant": "Discuss the evidence and understand your results.",
    "Saved research": "Your saved evidence cards, analyst reports and research watchlist.",
    "Monitoring": "Watchlist observations and worker activity.",
    "Stock universe": "Discover Indian cash equities across NSE and BSE.",
    "Settings": "Manage connections and understand data availability.",
}


def main() -> None:
    st.session_state.setdefault(
        "workspace_page",
        "Overview" if os.getenv("STOCK_RESEARCH_TEST_FIXTURES") == "1" else "Stock workspace",
    )
    sidebar_navigation()
    dataset = select_dataset()
    if dataset is None:
        for key in RESULT_KEYS:
            if key != "idea_cards":
                st.session_state.pop(key, None)
    sidebar_workspace(dataset)
    provider, model = model_controls()
    st.caption("THE EQUITY LEDGER  /  INDIA CASH EQUITIES  /  RESEARCH EDITION")
    page = st.selectbox(
        "Workspace", list(PAGES), key="workspace_page", width=230, label_visibility="collapsed"
    )
    research_page = page not in {
        "Monitoring",
        "Stock universe",
        "Settings",
        "Saved research",
        "Stock ideas",
    }
    if page != "Stock workspace":
        with st.container(
            horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"
        ):
            st.title(page, width="content")
            if research_page and dataset:
                st.badge(
                    "DEMO / NOT LIVE" if dataset["is_synthetic"] else "HISTORICAL / NOT LIVE",
                    color="orange" if dataset["is_synthetic"] else "gray",
                )
    if research_page and dataset is None:
        st.info(
            "Choose a prepared stock from Historical library, or upload a historical CSV in Research data. Saved research, stock search and settings remain accessible."
        )
        st.stop()
    if research_page and page != "Stock workspace":
        st.caption(
            dataset["symbol"].replace("DEMO_", "").replace("_", " ").title()
            + " · "
            + (
                f"Fictional data · Daily bars · As of {dataset['candles'][-1]['timestamp']}"
                if dataset["is_synthetic"]
                else f"Historical research · As of {dataset['candles'][-1]['timestamp']} · Source and adjustments in data context"
            )
        )
    elif not research_page:
        st.caption(PAGES[page])
    if page == "Stock workspace":
        stock_workspace(
            dataset,
            {
                "Overview": lambda: None,
                "Chart & indicators": lambda: price_liquidity(dataset),
                "Strategies & backtest": lambda: backtest_lab(dataset),
                "Validation": lambda: validation_lab(dataset),
                "Stock scenarios": lambda: monte_carlo_lab(dataset),
                "Evidence & reports": lambda: research_brief(dataset, provider, model),
                "Assistant": lambda: chatbot(dataset, provider, model),
            },
            on_assess=lambda: record_analysis(
                dataset, EngineClient().analyze(dataset["candles"], **market_options(dataset))
            ),
        )
    elif page == "Overview":
        overview(dataset, provider, model)
    elif page == "Market analysis":
        price_liquidity(dataset)
    elif page == "Stock ideas":
        stock_ideas(dataset)
    elif page == "Backtesting":
        backtest_lab(dataset)
    elif page == "Monte Carlo":
        monte_carlo_lab(dataset)
    elif page == "Validation":
        validation_lab(dataset)
    elif page == "Assistant":
        chatbot(dataset, provider, model)
    elif page == "Monitoring":
        monitoring()
    elif page == "Stock universe":
        stock_catalogue()
    elif page == "Saved research":
        saved_research()
    else:
        settings(provider, model)
    st.divider()
    st.caption(
        "Equity · Research edition     /     India cash equities     /     Results depend on supplied data and assumptions"
    )


if __name__ == "__main__":
    main()
