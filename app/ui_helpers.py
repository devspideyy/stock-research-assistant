"""Small presentation helpers; financial calculations belong to the C++ engine."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from app.animations import add_replay
from app.assessment import STRATEGIES, STRATEGY_GUIDE


COLORS = {
    "accent": "#214B3C",
    "positive": "#317359",
    "negative": "#A34D47",
    "muted": "#879388",
    "secondary": "#B59254",
}


def number(value: Any, digits: int = 2, *, prefix: str = "") -> str:
    """Format optional engine outputs without turning missing evidence into zero."""
    try:
        if value is None or pd.isna(value):
            return "Unavailable"
        return f"{prefix}{float(value):,.{digits}f}"
    except (ValueError, TypeError):
        return "Unavailable"


def percent(value: Any) -> str:
    try:
        return "Unavailable" if value is None else f"{float(value):.2%}"
    except (ValueError, TypeError):
        return "Unavailable"


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def plain_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(
            value.get("text")
            or value.get("message")
            or value.get("description")
            or value.get("title")
            or value.get("headline")
            or json.dumps(value, ensure_ascii=False, default=str)
        )
    return str(value)


def show_items(items: Any, empty_message: str = "No evidence supplied.") -> None:
    values = as_list(items)
    if not values:
        st.caption(empty_message)
    for value in values:
        st.markdown(f"- {plain_text(value)}")


def candle_frame(candles: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(candles)
    if "timestamp" in frame:
        frame["timestamp"] = frame["timestamp"].astype(str)
    return frame


def chart_layout(figure: go.Figure, *, height: int = 440) -> go.Figure:
    figure.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=12, r=18, t=24, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.06, x=0),
        hovermode="x unified",
        font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#506257"),
        colorway=[COLORS["accent"], COLORS["secondary"], "#697E91", COLORS["negative"]],
    )
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(gridcolor="rgba(140,150,170,0.12)", zeroline=False)
    return figure


def price_chart(
    candles: list[dict], analysis: dict | None = None, overlays: list[str] | None = None
) -> go.Figure:
    frame = candle_frame(candles)
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.04
    )
    fig.add_trace(
        go.Candlestick(
            x=frame.timestamp,
            open=frame.open,
            high=frame.high,
            low=frame.low,
            close=frame.close,
            name="Price",
            increasing_line_color=COLORS["positive"],
            decreasing_line_color=COLORS["negative"],
        ),
        row=1,
        col=1,
    )
    series = (analysis or {}).get("series", [])
    series_frame = pd.DataFrame(series)
    for index, indicator in enumerate(overlays or []):
        if indicator in series_frame and "timestamp" in series_frame:
            fig.add_trace(
                go.Scatter(
                    x=series_frame.timestamp,
                    y=series_frame[indicator],
                    name=indicator.upper(),
                    mode="lines",
                    line=dict(width=1.5, color=[COLORS["accent"], COLORS["secondary"]][index % 2]),
                ),
                row=1,
                col=1,
            )
    fig.add_trace(
        go.Bar(
            x=frame.timestamp,
            y=frame.volume,
            name="Volume",
            marker_color=COLORS["muted"],
            opacity=0.6,
        ),
        row=2,
        col=1,
    )
    fig.update_xaxes(type="category", nticks=8, rangeslider_visible=False)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return chart_layout(fig, height=420)


def depth_chart(bids: list[dict], asks: list[dict]) -> go.Figure:
    fig = go.Figure()
    for name, values, color in [
        ("Displayed bids", bids, COLORS["positive"]),
        ("Displayed asks", asks, COLORS["negative"]),
    ]:
        fig.add_trace(
            go.Bar(
                x=[item["quantity"] for item in values],
                y=[str(item["price"]) for item in values],
                name=name,
                orientation="h",
                marker_color=color,
            )
        )
    fig.update_layout(barmode="group", xaxis_title="Displayed quantity", yaxis_title="Price level")
    return chart_layout(fig, height=320)


def equity_charts(results: dict[str, dict], *, replay: bool = False) -> tuple[go.Figure, go.Figure]:
    equity, drawdown = go.Figure(), go.Figure()
    palette = [COLORS["accent"], COLORS["secondary"], "#697E91", "#A34D47", "#879388"]
    for index, (label, result) in enumerate(results.items()):
        rows = result.get("equity", [])
        color = palette[index % len(palette)]
        equity.add_trace(
            go.Scatter(
                x=[r["timestamp"] for r in rows],
                y=[r["equity"] for r in rows],
                name=label,
                line=dict(color=color, width=2),
            )
        )
        drawdown.add_trace(
            go.Scatter(
                x=[r["timestamp"] for r in rows],
                y=[r["drawdown"] for r in rows],
                name=label,
                line=dict(color=color, width=1.6),
            )
        )
    for fig in (equity, drawdown):
        fig.update_xaxes(type="category", nticks=8)
    equity.update_layout(yaxis_title="Portfolio value")
    drawdown.update_layout(yaxis_title="Drawdown", yaxis_tickformat=".0%")
    equity = chart_layout(equity)
    return (add_replay(equity, label="Observed bar") if replay else equity), chart_layout(
        drawdown, height=270
    )


def simulation_chart(result: dict, *, replay: bool = False) -> go.Figure:
    fig = go.Figure()
    for index, path in enumerate(result.get("sample_paths", [])[:12]):
        fig.add_trace(
            go.Scatter(
                x=list(range(len(path))),
                y=path,
                mode="lines",
                line=dict(color="rgba(67,109,84,0.16)", width=1),
                name="Sample scenarios",
                showlegend=index == 0,
                hoverinfo="skip",
            )
        )
    rows = result.get("percentiles", [])
    steps = [r["step"] for r in rows]
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=[r["p05"] for r in rows],
            mode="lines",
            line=dict(width=0),
            name="5th percentile",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=[r["p95"] for r in rows],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(181,146,84,0.17)",
            name="5th–95th percentile",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=[r["p50"] for r in rows],
            mode="lines",
            line=dict(color=COLORS["accent"], width=2.5),
            name="Median scenario",
        )
    )
    fig.update_layout(
        xaxis_title="Future observations (daily bars = trading days)",
        yaxis_title="Simulated investment value",
    )
    fig = chart_layout(fig)
    return add_replay(fig, label="Scenario step") if replay else fig


def trade_chart(candles: list[dict], result: dict) -> go.Figure:
    start = result.get("evaluation", {}).get("start", candles[0]["timestamp"])
    figure = price_chart([row for row in candles if row["timestamp"] >= start])
    for side, color, marker in [
        ("BUY", COLORS["positive"], "triangle-up"),
        ("SELL", COLORS["negative"], "triangle-down"),
    ]:
        trades = [row for row in result.get("trades", []) if row["side"] == side]
        figure.add_trace(
            go.Scatter(
                x=[row["timestamp"] for row in trades],
                y=[row["price"] for row in trades],
                mode="markers",
                name=f"Simulated {side.lower()}",
                marker=dict(color=color, symbol=marker, size=11),
            ),
            row=1,
            col=1,
        )
    return figure


def terminal_distribution(result: dict) -> go.Figure:
    bins = result.get("terminal_histogram", [])
    figure = go.Figure(
        go.Bar(
            x=[(row["low"] + row["high"]) / 2 for row in bins],
            y=[row["count"] for row in bins],
            marker_color=COLORS["accent"],
            name="Simulated path count",
        )
    )
    figure.update_layout(xaxis_title="Terminal investment value", yaxis_title="Simulated paths")
    return chart_layout(figure, height=340)


def render_evidence(evidence: dict) -> None:
    st.caption(f"Evidence as of {evidence.get('as_of', evidence.get('created_at', 'unavailable'))}")
    st.write(f"**Horizon:** {evidence.get('horizon', 'Research horizon not supplied')}")
    action = evidence.get("action") or evidence.get("decision")
    if action:
        st.info(f"Research stance: {plain_text(action)}")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Supporting evidence")
        show_items(evidence.get("supporting", evidence.get("supporting_evidence")))
        st.markdown("#### Missing information")
        show_items(
            evidence.get("missing", evidence.get("missing_data")), "No missing fields listed."
        )
    with right:
        st.markdown("#### Opposing evidence")
        show_items(evidence.get("opposing", evidence.get("opposing_evidence")))
        st.markdown("#### Invalidation conditions")
        show_items(
            evidence.get(
                "invalidations",
                evidence.get("invalidation", evidence.get("invalidation_conditions")),
            )
        )
    with st.expander("Inspect the complete evidence record"):
        st.json(evidence, expanded=False)


def render_report(report: dict) -> None:
    mode = report.get("mode") or report.get("provider", "rules")
    st.caption(
        f"Report mode: {mode}. Model text interprets saved evidence; calculations come from the engine."
    )
    roles = report.get("roles") or report.get("agents") or report.get("analysts")
    if isinstance(roles, Mapping):
        for name, content in roles.items():
            with st.expander(str(name).replace("_", " ").title(), expanded=True):
                if isinstance(content, Mapping) and content.get("text"):
                    st.write(content["text"])
                    if content.get("citations"):
                        st.caption(
                            "Evidence references: " + ", ".join(map(str, content["citations"]))
                        )
                elif isinstance(content, Mapping):
                    st.json(content, expanded=False)
                else:
                    st.write(content)
    elif isinstance(roles, list):
        for item in roles:
            if isinstance(item, Mapping):
                st.markdown(f"**{item.get('role', item.get('name', 'Analyst'))}**")
                st.write(item.get("content", item.get("analysis", item)))
    for key in ("summary", "review", "conclusion", "answer", "text"):
        if report.get(key):
            st.write(report[key])
    with st.expander("Complete report and provenance"):
        st.json(report, expanded=False)


def json_download(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def render_assessment(card: dict) -> None:
    assessment = card.get("assessment")
    if not assessment or assessment["bullish"] is None:
        st.info(
            "Assessment unavailable. Confirm daily bars, provenance and valid prices, then rebuild the evidence card with at least 21 observations."
        )
        if card.get("missing"):
            with st.expander("Data checks and missing evidence"):
                show_items(card["missing"])
        return
    with st.container(border=True):
        st.caption("STOCK RESEARCH RECOMMENDATION / " + assessment["scope"].upper())
        st.markdown("### " + assessment["recommendation"])
        st.caption(
            f"{card['symbol']} · As of {card['as_of']} · {assessment['regime']} · {assessment['risk']}"
        )
        columns = st.columns(3)
        columns[0].metric("Bullish evidence / 100", assessment["bullish"])
        columns[1].metric("Bearish evidence / 100", assessment["bearish"])
        columns[2].metric("Scorable factor weight / 100", assessment["coverage"])
        st.caption(
            "Fixed heuristic points—not a probability of profit or an independently validated stock rating. Opposing cases can both have support."
        )
        if card["data_quality"].get("synthetic") or card["data_quality"].get("historical"):
            st.warning(
                "This assessment describes demo/history only. It cannot be used as a current stock recommendation."
            )
        st.caption(
            f"Research gate: {card['action']} · Long-only cash research; no automated orders."
        )
        with st.expander("Why this rating? Inspect every factor"):
            st.dataframe(pd.DataFrame(assessment["factors"]), hide_index=True, width="stretch")
            show_items(assessment["limitations"])
        st.markdown("**Strategy hypotheses to test**")
        labels = {value: key for key, value in STRATEGIES.items()}
        for strategy in assessment["strategies"]:
            st.write(f"**{labels[strategy]}** · {STRATEGY_GUIDE[strategy][1]}")
        if not assessment["strategies"]:
            st.write(
                "Wait / cash benchmark. No long setup is favoured by these rules; bearish is not a short-sale instruction."
            )
        with st.expander("Invalidation and missing evidence"):
            show_items(assessment["invalidation"])
            show_items(card.get("missing"))
            support = next((fact["text"] for fact in card["facts"] if fact["id"] == "P2"), None)
            if support:
                st.caption(support)
