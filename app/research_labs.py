"""Interactive indicator catalogue and real, key-free stock identifiers."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import indicators, instruments
from app.ui_helpers import chart_layout, number


def indicator_lab(dataset: dict) -> None:
    catalogue = indicators.catalogue()
    st.markdown("### Indicator library")
    if not catalogue:
        st.info("Install the updated project requirements to enable TA-Lib.")
        return
    st.caption(
        f"{len(catalogue)} TA-Lib functions: trend, momentum, volatility, volume, patterns, "
        "cycles and statistical/math tools. Calculate a selected function with your own parameters. "
        "Indicators remain supporting evidence; this lab does not alter strategy rules."
    )
    groups = sorted({row["group"] for row in catalogue.values()})
    group = st.selectbox("Indicator family", ["All families", *groups], key="indicator_group")
    names = [
        name for name, row in catalogue.items() if group == "All families" or row["group"] == group
    ]
    name = st.selectbox(
        "Indicator function",
        names,
        index=names.index("RSI") if "RSI" in names else 0,
        format_func=lambda item: f"{item} · {catalogue[item]['display_name']}",
        key="indicator_function",
    )
    info = catalogue[name]
    with st.form(f"indicator_parameters_{name}"):
        settings = {}
        price_inputs = {}
        for key, value in info["inputs"].items():
            if isinstance(value, str) and value in indicators.FIELDS:
                price_inputs[key] = st.selectbox(
                    f"{key} input column",
                    indicators.FIELDS,
                    index=indicators.FIELDS.index(value),
                    key=f"input_{name}_{key}",
                )
        variable_period = 20
        if "periods" in info["inputs"].values():
            variable_period = int(st.number_input("MAVP constant period schedule", 2, 10_000, 20))
            st.caption(
                "This lab supplies an explicitly constant schedule to MAVP; it is not adaptive tuning."
            )
        for key, default in info["parameters"].items():
            label = key.replace("_", " ")
            if key.endswith("matype"):
                settings[key] = st.selectbox(
                    label,
                    list(range(9)),
                    index=default,
                    format_func=lambda value: [
                        "SMA",
                        "EMA",
                        "WMA",
                        "DEMA",
                        "TEMA",
                        "TRIMA",
                        "KAMA",
                        "MAMA",
                        "T3",
                    ][value],
                )
            elif isinstance(default, int):
                settings[key] = int(st.number_input(label, 0, 10_000, default, step=1))
            else:
                settings[key] = float(st.number_input(label, value=float(default), format="%.5f"))
        if st.form_submit_button("Calculate selected indicator"):
            try:
                st.session_state.indicator_result = indicators.calculate(
                    dataset["candles"],
                    name,
                    settings,
                    price_inputs,
                    variable_period,
                )
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
    result = st.session_state.get("indicator_result")
    if result:
        st.markdown(f"#### Last calculation: {result['function']} · {result['display_name']}")
        st.caption(
            f"Source: {dataset['symbol']} · Warm-up: {result['lookback_bars']} bars · "
            "Warm-up and invalid-domain values remain missing. Recalculate after editing settings."
        )
        st.json(
            {"parameters": result["parameters"], "input_columns": result["input_columns"]},
            expanded=False,
        )
        columns = st.columns(len(result["latest"]))
        for column, (label, value) in zip(columns, result["latest"].items(), strict=True):
            column.metric(label, number(value, 4))
        figure = go.Figure()
        for label, values in result["columns"].items():
            if result["group"] == "Pattern Recognition":
                figure.add_bar(x=result["timestamps"], y=values, name=label)
            else:
                figure.add_scatter(x=result["timestamps"], y=values, name=label, connectgaps=False)
        st.plotly_chart(chart_layout(figure, height=340), width="stretch")
        if result["domain_gaps"]:
            st.warning(
                "Some values are outside this function's numeric domain and are shown as missing."
            )
        if result["group"] == "Pattern Recognition":
            st.caption(
                "Pattern codes are library detections, not probabilities, confidence scores or trade recommendations."
            )
        if result["function"] in {"BETA", "CORREL"}:
            st.caption(
                "This compares the selected OHLCV columns. It is not market beta or stock-to-index correlation."
            )
        csv = pd.DataFrame({"timestamp": result["timestamps"], **result["columns"]}).to_csv(
            index=False
        )
        st.download_button(
            "Download indicator CSV",
            csv,
            file_name=f"{dataset['symbol']}_{result['function']}.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download indicator settings and provenance",
            json.dumps(result, allow_nan=False, indent=2),
            file_name="indicator_experiment.json",
            mime="application/json",
        )
        st.caption(
            "Calculated by the compiled TA-Lib library through Python. The C++ evidence/backtest "
            "engine remains separate; smoothing seeds and warm-up conventions may differ."
        )
    with st.expander(f"Browse all {len(catalogue)} installed functions"):
        st.dataframe(
            pd.DataFrame(
                [
                    {"Function": name, "Description": row["display_name"], "Family": row["group"]}
                    for name, row in catalogue.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )


def stock_catalogue() -> None:
    st.markdown("### Indian cash-equity catalogue")
    st.write(
        "Search the NSE and BSE cash equities in the provider's instrument files. "
        "This catalogue contains real identifiers and company names. Prices are not connected yet."
    )
    st.caption("No key required. Refresh downloads the public beginning-of-day instrument files.")
    if st.button("Refresh NSE and BSE stock catalogue"):
        try:
            with st.spinner("Downloading and validating the official instrument lists…"):
                instruments.refresh_catalogue()
            st.success("Stock identifiers refreshed. This does not start live prices.")
        except (OSError, ValueError) as exc:
            st.error(f"Refresh failed; any previous complete catalogue is preserved. {exc}")
    try:
        data = instruments.load_catalogue()
    except (OSError, ValueError) as exc:
        st.error(str(exc))
        return
    if not data:
        st.info("Refresh the catalogue to enable stock search.")
        return
    rows = data["instruments"]
    counts = st.columns(3)
    counts[0].metric("NSE listings", sum(row["exchange"] == "NSE" for row in rows))
    counts[1].metric("BSE listings", sum(row["exchange"] == "BSE" for row in rows))
    counts[2].metric("Distinct ISINs", len({row["isin"] for row in rows}))
    st.caption(
        f"Identifiers fetched at {data['fetched_at']} · The same company can have listings on both exchanges."
    )
    exchanges = st.multiselect("Catalogue exchanges", ["NSE", "BSE"], default=["NSE", "BSE"])
    query = (
        st.text_input("Search stock symbol, company or ISIN", placeholder="RELIANCE, Tata, INE…")
        .strip()
        .casefold()
    )
    matched = [
        row
        for row in rows
        if row["exchange"] in exchanges
        and (
            not query
            or query in " ".join(row[key] for key in ("trading_symbol", "name", "isin")).casefold()
        )
    ]
    st.caption(
        f"{len(matched):,} matching listings. Showing up to 500; refine the search for a particular company."
    )
    if matched:
        st.dataframe(pd.DataFrame(matched[:500]), hide_index=True, width="stretch")
        selected = st.selectbox(
            "Stock identifier",
            matched[:500],
            format_func=lambda row: f"{row['exchange']} · {row['trading_symbol']} · {row['name']}",
        )
        st.code(selected["instrument_key"], language=None)
        st.caption(
            "Viewing this identifier does not change the research dataset selected in the sidebar. "
            "Live quotes and price history require your permitted broker token and data connection."
        )
    st.info(
        "All-stock search and simultaneous live streaming have different limits. "
        "Use the complete catalogue for discovery, then stream selected symbols within the provider's quota. "
        "Today's catalogue also excludes delisted history, so it is not a survivorship-free historical universe."
    )
    st.link_button(
        "Free data and key setup guide",
        "https://upstox.com/developer/api-documentation/analytics-token/",
    )
