"""One stock, one historical window, with research and experiments in context."""

import streamlit as st
from app.research_protocol import visible_candles
from app.evaluation_ui import source_health, experiment_context, rating_panel
from app.workspace import go_stock_section

from app.ui_helpers import number, percent, render_assessment


def stock_workspace(dataset: dict, panels: dict, on_assess=None) -> None:
    candles = visible_candles(dataset)
    st.title(dataset.get("name", dataset["symbol"]))
    st.caption(
        f"NSE · {dataset['symbol']} · {candles[0]['timestamp']} — {candles[-1]['timestamp']} · "
        "Daily history · Prices and results belong to this selected stock and window."
    )
    section = (
        st.segmented_control(
            "Research section",
            list(panels),
            default="Overview",
            key="stock_section",
            format_func=lambda section: {
                "Chart & indicators": "Charts",
                "Strategies & backtest": "Backtest",
                "Risk / Monte Carlo": "Monte Carlo",
                "Evidence & reports": "Evidence",
            }.get(section, section),
            width="stretch",
        )
        or "Overview"
    )
    source_health(dataset)
    experiment_context()
    if section != "Overview":
        panels[section or "Overview"]()
        return
    last = candles[-1]
    a, b, c = st.columns(3)
    a.metric("Historical close · research units", number(last["close"], prefix="₹ "), border=True)
    b.metric("Last daily change", percent(last["close"] / candles[-2]["close"] - 1), border=True)
    c.metric("Observations", f"{len(candles):,}", border=True)
    main, desk = st.columns([3, 1], gap="large")
    with main:
        st.subheader("The research record")
        st.write(
            "Explore this stock's candles, volume, indicators and simulated trade markers in one research chart."
        )
        st.button(
            "Open research chart",
            type="primary",
            on_click=go_stock_section,
            args=("Chart & indicators",),
        )
        st.caption(
            "The selected source and dates govern every calculation. Historical research through 2020."
        )
    with desk:
        with st.container(border=True):
            st.caption("RESEARCH NOTE")
            st.subheader("Your research desk")
            st.write(
                "Inspect the stock's record, test a fixed rule, then examine how fragile its returns may be."
            )
            if st.button("Assess this stock", type="primary", disabled=on_assess is None):
                try:
                    with st.spinner("Building the historical price-evidence case…"):
                        on_assess()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.error(str(exc))
            st.button(
                "Test a strategy",
                on_click=go_stock_section,
                args=("Strategies & backtest",),
                width="stretch",
            )
            st.button(
                "Explore Monte Carlo",
                on_click=go_stock_section,
                args=("Risk / Monte Carlo",),
                width="stretch",
            )
            st.caption("01 Inspect the record · 02 Backtest a rule · 03 Explore risk")
        st.caption("News connector · Pending\n\nDerivatives / Level 2–3 · Deferred")
    evidence = st.session_state.get("evidence")
    if evidence:
        case = evidence.get("assessment", {})
        with st.expander(
            f"Price-evidence case · Bull {case.get('bullish', '?')} / Bear {case.get('bearish', '?')}",
            expanded=True,
        ):
            render_assessment(evidence)
    rating_panel(dataset)
    quality = dataset.get("history_quality", {})
    with st.expander("Historical sources & data quality"):
        st.write(dataset["description"])
        if quality:
            st.caption(
                f"[Price source]({quality.get('source', '')}) · Revision {quality.get('revision', 'unrecorded')[:12]}"
            )
            st.json(quality, expanded=False)
        else:
            st.caption(
                "User-supplied history. Inspect the source and corporate-action convention before interpreting results."
            )
