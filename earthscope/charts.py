"""Plotly figures."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .statistics import TrendResult

# Fixed categorical order: primary location first, comparison second.
SERIES_COLORS = ["#2a78d6", "#eb6834"]


def trend_figure(
    series: list[tuple[str, pd.DataFrame, TrendResult]], variable_label: str, unit: str
) -> go.Figure:
    """Annual means with the fitted line for one or two locations (same unit).

    The fitted line spans only the observed years; nothing is extrapolated.
    """
    fig = go.Figure()
    multiple = len(series) > 1
    for index, (name, annual, trend) in enumerate(series):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=annual["year"],
                y=annual["annual_mean"],
                mode="lines+markers",
                name=f"{name} — annual mean" if multiple else "Annual mean",
                line=dict(color=color, width=2),
                marker=dict(size=8, color=color, line=dict(width=2, color="white")),
                hovertemplate=f"%{{x}}: %{{y:.2f}} {unit}<extra>{name}</extra>",
            )
        )
        if trend.slope is not None and trend.intercept is not None and len(annual) >= 2:
            ends = [int(annual["year"].min()), int(annual["year"].max())]
            fig.add_trace(
                go.Scatter(
                    x=ends,
                    y=trend.fitted(ends),
                    mode="lines",
                    name=f"{name} — linear trend" if multiple else "Linear trend",
                    line=dict(color=color, width=2, dash="dash"),
                    hovertemplate=f"Fitted %{{x}}: %{{y:.2f}} {unit}<extra>{name}</extra>",
                )
            )
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title=f"Annual mean {variable_label} ({unit})",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=440,
    )
    fig.update_xaxes(dtick=5, showgrid=False)
    return fig
