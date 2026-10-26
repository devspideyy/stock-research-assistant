"""One stock, one historical window, with research and experiments in context."""

import streamlit as st
from app.research_protocol import visible_candles
from app.evaluation_ui import source_health, experiment_context, rating_panel
from app.workspace import go_stock_section

from app.ui_helpers import number, percent, render_assessment


def stock_workspace(dataset: dict, panels: dict, on_assess=None) -> None:
    candles = visible_candles(dataset)
    title, status = st.columns([4, 1], vertical_alignment="center")
    title.title(dataset.get("name", dataset["symbol"]))
    status.badge(
        "Demo" if dataset["is_synthetic"] else "Historical",
        color="orange" if dataset["is_synthetic"] else "gray",
    )
    st.caption(
        f"NSE / {dataset['symbol']} / {candles[0]['timestamp'][:10]} - {candles[-1]['timestamp'][:10]}"
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
            label_visibility="collapsed",
        )
        or "Overview"
    )
    if section != "Overview":
        panels[section]()
        source_health(dataset)
        experiment_context()
        return
    last = candles[-1]
    a, b, c = st.container(key="overview_metrics").columns(3)
    a.metric("Historical close", number(last["close"], prefix="₹ "), border=True)
    b.metric("Daily change", percent(last["close"] / candles[-2]["close"] - 1), border=True)
    c.metric("Sessions", f"{len(candles):,}", border=True)
    actions = st.container(key="overview_actions").columns(4)
    actions[0].button(
        "Open research chart",
        type="primary",
        on_click=go_stock_section,
        args=("Chart & indicators",),
        width="stretch",
    )
    actions[1].button(
        "Test a strategy",
        on_click=go_stock_section,
        args=("Strategies & backtest",),
        width="stretch",
    )
    actions[2].button(
        "Explore Monte Carlo",
        on_click=go_stock_section,
        args=("Risk / Monte Carlo",),
        width="stretch",
    )
    if actions[3].button("Assess this stock", disabled=on_assess is None, width="stretch"):
        try:
            with st.spinner("Assessing price evidence..."):
                on_assess()
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    evidence = st.session_state.get("evidence")
    if evidence:
        case = evidence.get("assessment", {})
        with st.expander(
            f"Price-evidence case · Bull {case.get('bullish', '?')} / Bear {case.get('bearish', '?')}",
            expanded=True,
        ):
            render_assessment(evidence)
    source_health(dataset)
    experiment_context()
    with st.expander("Research methods and sources"):
        rating_panel(dataset)
        st.write(dataset["description"])
        st.json(dataset.get("history_quality", {}), expanded=False)
