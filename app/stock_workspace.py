"""One stock, one historical window, with research and experiments in context."""

import streamlit as st

from app.ui_helpers import number, percent, price_chart, render_assessment


def stock_workspace(dataset: dict, panels: dict, on_assess=None) -> None:
    candles = dataset["candles"]
    st.caption("THE EQUITY LEDGER  /  STOCK RESEARCH")
    st.title(dataset.get("name", dataset["symbol"]))
    st.caption(
        f"NSE · {dataset['symbol']} · {candles[0]['timestamp']} — {candles[-1]['timestamp']} · "
        "Daily history · Prices and results belong to this selected stock and window."
    )
    section = st.segmented_control(
        "Research section", list(panels), default="Overview", key="stock_section", width="stretch"
    )
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
        st.subheader("The price record")
        range_ = st.segmented_control(
            "Visible chart range", ["6M", "1Y", "5Y", "All"], default="1Y"
        )
        count = {"6M": 126, "1Y": 252, "5Y": 1260, "All": len(candles)}[range_ or "1Y"]
        st.plotly_chart(
            price_chart(candles[-count:]), width="stretch", config={"displayModeBar": False}
        )
        st.caption(
            "Chart range changes the view. The research window above controls calculations. Historical prices; no live feed."
        )
    with desk:
        with st.container(border=True):
            st.caption("RESEARCH NOTE")
            st.subheader("Read. Test. Challenge.")
            st.write(
                "Inspect the stock's record, test a fixed rule, then examine how fragile its returns may be."
            )
            if st.button("Assess this stock", type="primary", disabled=on_assess is None):
                try:
                    with st.spinner("Building the historical price-evidence case…"):
                        on_assess()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.error(str(exc))
            st.caption(
                "01  Chart & indicators\n\n02  Strategies & backtest\n\n03  Validation\n\n04  Evidence & assistant"
            )
        st.caption("News connector · Pending\n\nDerivatives / Level 2–3 · Deferred")
    evidence = st.session_state.get("evidence")
    if evidence:
        case = evidence.get("assessment", {})
        with st.expander(
            f"Price-evidence case · Bull {case.get('bullish', '?')} / Bear {case.get('bearish', '?')}",
            expanded=True,
        ):
            render_assessment(evidence)
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
