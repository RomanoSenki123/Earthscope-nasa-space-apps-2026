"""Plotly figures in the Ocean Observatory style.

Every trace is drawn from the annual table and the fitted trend passed in; no
value is generated here.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .statistics import TrendResult

SERIES_TEAL = "#0893A3"  # model-derived annual values
TREND_CORAL = "#DC6426"  # fitted line with a positive slope (3.6:1 against white)
TREND_NEUTRAL = "#34465B"  # fitted line with a zero or negative slope
COMPARE_VIOLET = "#6250D6"  # second location in comparison charts
INK = "#10233D"
GRID = "#E5EDF4"
SURFACE = "#FFFFFF"


def trend_color(trend: TrendResult) -> str:
    """Coral marks an upward fitted trend; other directions use a neutral line."""
    return TREND_CORAL if trend.slope is not None and trend.slope > 0 else TREND_NEUTRAL


def _fit_trace(annual: pd.DataFrame, trend: TrendResult, name: str, color: str, unit: str, tag: str):
    """Fitted line across the observed years only (never extrapolated)."""
    years = annual["year"].sort_values()
    return go.Scatter(
        x=years,
        y=trend.fitted(years),
        mode="lines",
        name=name,
        line=dict(color=color, width=2.5, dash="dash"),
        hovertemplate=f"Fitted line: %{{y:.2f}} {unit}<extra>{tag}</extra>",
    )


def _layout(fig: go.Figure, variable_label: str, unit: str) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK, size=14, family="Arial, Helvetica, sans-serif"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=SURFACE, font=dict(color=INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=64, r=16, t=48, b=12),
        height=420,
    )
    fig.update_xaxes(title_text="Year", tickformat="d", nticks=6, tickangle=0, showgrid=False, linecolor=GRID, ticks="outside", tickcolor=GRID)
    # The card heading names the variable, so the axis title stays short and readable.
    fig.update_yaxes(
        title_text=f"Annual mean ({unit})", gridcolor=GRID, zeroline=False, automargin=True,
        title_standoff=12,
    )
    fig.update_xaxes(automargin=True)
    return fig


def trend_figure(annual: pd.DataFrame, trend: TrendResult, variable_label: str, unit: str) -> go.Figure:
    """Annual means for one location with its fitted linear trend."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=annual["year"],
            y=annual["annual_mean"],
            mode="lines+markers",
            name="Annual mean",
            line=dict(color=SERIES_TEAL, width=2),
            marker=dict(size=8, color=SERIES_TEAL, line=dict(width=2, color=SURFACE)),
            hovertemplate=f"Annual mean: %{{y:.2f}} {unit}<extra></extra>",
        )
    )
    if trend.slope is not None and trend.intercept is not None and len(annual) >= 2:
        fig.add_trace(
            _fit_trace(annual, trend, "Fitted trend", trend_color(trend), unit, "")
        )
    return _layout(fig, variable_label, unit)


def comparison_figure(
    series: list[tuple[str, pd.DataFrame, TrendResult]], variable_label: str, unit: str
) -> go.Figure:
    """Annual means and fitted lines for two locations on one shared axis.

    Colour identifies the location (fixed order: main, then comparison);
    solid lines are annual values and dashed lines are fitted trends.
    """
    colors = [SERIES_TEAL, COMPARE_VIOLET]
    fig = go.Figure()
    for index, (name, annual, trend) in enumerate(series[: len(colors)]):
        color = colors[index]
        fig.add_trace(
            go.Scatter(
                x=annual["year"],
                y=annual["annual_mean"],
                mode="lines+markers",
                name=name,
                line=dict(color=color, width=2),
                marker=dict(size=7, color=color, line=dict(width=2, color=SURFACE)),
                hovertemplate=f"%{{y:.2f}} {unit}<extra>{name}</extra>",
            )
        )
        if trend.slope is not None and trend.intercept is not None and len(annual) >= 2:
            fit = _fit_trace(annual, trend, f"{name} — fitted trend", color, unit, name)
            fit.showlegend = False  # colour already identifies the location
            fig.add_trace(fit)
    return _layout(fig, variable_label, unit)
