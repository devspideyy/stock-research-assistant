"""Bounded browser-side playback of completed C++ results; no recalculation loop."""

from __future__ import annotations

import math

import plotly.graph_objects as go


def positions(length: int, limit: int) -> list[int]:
    if length < 2:
        return list(range(length))
    count = min(length, limit)
    return sorted({round(i * (length - 1) / (count - 1)) for i in range(count)})


def add_replay(figure: go.Figure, *, label: str) -> go.Figure:
    """Stable traces/axes, ≤36 frames and ≤300 displayed points per trace."""
    if not figure.data or len(figure.data[0].x) < 2:
        return figure
    original = list(figure.data)
    length = len(original[0].x)
    shown = positions(length, 300)
    ends = [shown[i] for i in positions(len(shown), 36)]

    def traces_at(end):
        selected = [i for i in shown if i <= end]
        if not selected or selected[-1] != end:
            selected.append(end)
        traces = []
        for trace in original:
            values = trace.to_plotly_json()
            values["x"] = [trace.x[i] for i in selected]
            values["y"] = [trace.y[i] for i in selected]
            traces.append(go.Scatter(values))
        return traces

    result = go.Figure(data=traces_at(length - 1), layout=figure.layout)

    def annotation(end):
        return dict(
            text=f"{label}: {original[0].x[end]}",
            x=1,
            y=1.12,
            xref="paper",
            yref="paper",
            xanchor="right",
            showarrow=False,
            font=dict(color="#A9BBD1", size=10),
        )

    result.frames = [
        go.Frame(
            name=str(original[0].x[end]),
            data=traces_at(end),
            layout=dict(annotations=[annotation(end)]),
        )
        for end in ends
    ]
    values = [
        float(value)
        for trace in original
        for value in trace.y
        if value is not None and math.isfinite(float(value))
    ]
    if values:
        low, high = min(values), max(values)
        padding = max((high - low) * 0.06, abs(high) * 0.005, 0.001)
        result.update_yaxes(range=[low - padding, high + padding], autorange=False)
    if figure.layout.xaxis.type == "category":
        result.update_xaxes(
            categoryorder="array",
            categoryarray=[original[0].x[i] for i in shown],
            range=[-0.5, len(shown) - 0.5],
            autorange=False,
        )
    else:
        result.update_xaxes(range=[original[0].x[0], original[0].x[-1]], autorange=False)
    instant = {
        "mode": "immediate",
        "frame": {"duration": 0, "redraw": True},
        "transition": {"duration": 0},
    }
    result.update_layout(
        height=(figure.layout.height or 440) + 100,
        margin=dict(l=12, r=18, t=24, b=120),
        annotations=[annotation(length - 1)],
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                x=0,
                y=-0.17,
                xanchor="left",
                yanchor="top",
                showactive=False,
                bgcolor="#192433",
                bordercolor="#33435A",
                font=dict(color="#E5EDF7"),
                buttons=[
                    dict(
                        label="▶ Play",
                        method="animate",
                        args=[
                            [frame.name for frame in result.frames],
                            {
                                "mode": "immediate",
                                "fromcurrent": False,
                                "frame": {"duration": 140, "redraw": True},
                                "transition": {"duration": 0},
                            },
                        ],
                    ),
                    dict(label="Ⅱ Pause", method="animate", args=[[None], instant]),
                ],
            )
        ],
        sliders=[
            dict(
                active=6,
                x=0.28,
                len=0.72,
                y=-0.14,
                bgcolor="#33435A",
                activebgcolor="#62D9BB",
                font=dict(color="#A9BBD1", size=9),
                currentvalue=dict(prefix="Scrub checkpoint: "),
                steps=[
                    dict(
                        label=result.frames[i].name,
                        method="animate",
                        args=[[result.frames[i].name], instant],
                    )
                    for i in positions(len(result.frames), 7)
                ],
            )
        ],
    )
    # Short series have fewer than seven scrub positions.
    result.layout.sliders[0].active = len(result.layout.sliders[0].steps) - 1
    return result
