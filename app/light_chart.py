"""Local candles and native fills rendered with the bundled Lightweight Charts library."""

from functools import lru_cache
import json
import math
from pathlib import Path

import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def assets(version: tuple) -> tuple[str, str]:
    return (
        (ROOT / "vendor/lightweight-charts.standalone.production.js").read_text(encoding="utf-8"),
        (ROOT / "chart_view.html").read_text(encoding="utf-8"),
    )


def chart_payload(
    candles, analysis=None, overlays=None, panels=None, trades=None, symbol=""
) -> dict:
    dates = {row["timestamp"] for row in candles}
    if len({stamp[:10] for stamp in dates}) != len(candles):
        raise ValueError("The research chart requires one completed bar per day.")
    bars = [
        {"time": row["timestamp"][:10], **{k: row[k] for k in ("open", "high", "low", "close")}}
        for row in candles
    ]
    volume = [
        {
            "time": row["timestamp"][:10],
            "value": row["volume"],
            "color": "#93B3A1" if row["close"] >= row["open"] else "#D4A29A",
        }
        for row in candles
    ]
    lines = []
    for name in overlays or []:
        values = [
            {"time": row["timestamp"][:10], "value": row[name]}
            for row in (analysis or {}).get("series", [])
            if row["timestamp"] in dates and row.get(name) is not None and math.isfinite(row[name])
        ]
        lines.append({"name": name.upper(), "data": values, "pane": 0})
    next_pane = 2
    for panel, values in (panels or {}).items():
        index = 0 if values.get("overlay") else next_pane
        if index:
            next_pane += 1
        for name, numbers in values["columns"].items():
            lines.append(
                {
                    "name": f"{panel} · {name}",
                    "pane": index,
                    "data": [
                        {"time": stamp[:10], "value": value}
                        for stamp, value in zip(values["timestamps"], numbers)
                        if stamp in dates and value is not None and math.isfinite(value)
                    ],
                }
            )
    fills = [
        {**row, "time": row["timestamp"][:10]} for row in trades or [] if row["timestamp"] in dates
    ]
    return {"symbol": symbol, "bars": bars, "volume": volume, "lines": lines, "fills": fills}


def chart_document(payload: dict) -> str:
    library, template = assets(
        (
            (ROOT / "chart_view.html").stat().st_mtime_ns,
            (ROOT / "vendor/lightweight-charts.standalone.production.js").stat().st_mtime_ns,
        )
    )
    # An inert JSON block with escaped '<' prevents imported labels closing the script tag.
    data = json.dumps(payload, allow_nan=False).replace("<", "\\u003c")
    return template.replace("/* BUNDLED_LIBRARY */", library).replace("/* PAYLOAD */", data)


def light_chart(
    candles, analysis=None, overlays=None, panels=None, trades=None, *, symbol=""
) -> None:
    payload = chart_payload(candles, analysis, overlays, panels, trades, symbol)
    extra_panes = sum(not values.get("overlay", False) for values in (panels or {}).values())
    components.html(chart_document(payload), height=610 + 150 * extra_panes, scrolling=False)
