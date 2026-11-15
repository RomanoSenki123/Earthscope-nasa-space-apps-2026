"""The figures must draw exactly the values they are given."""

import numpy as np
import pandas as pd

from earthscope import charts
from earthscope.statistics import calculate_linear_trend

YEARS = np.arange(1991, 2026)


def make(slope, seed=2):
    rng = np.random.default_rng(seed)
    annual = pd.DataFrame({"year": YEARS, "annual_mean": 27 + slope * (YEARS - 1991) + rng.normal(0, 0.1, YEARS.size)})
    return annual, calculate_linear_trend(annual["year"], annual["annual_mean"])


def test_trend_figure_plots_the_given_values_and_fit():
    annual, trend = make(0.03)
    fig = charts.trend_figure(annual, trend, "2-meter air temperature", "°C")
    actual, fitted = fig.data
    assert list(actual.x) == list(YEARS)
    assert np.allclose(actual.y, annual["annual_mean"])
    assert np.allclose(fitted.y, trend.intercept + trend.slope * YEARS)
    assert (min(fitted.x), max(fitted.x)) == (1991, 2025)  # never extrapolated
    assert actual.line.color == charts.SERIES_TEAL and fitted.line.dash == "dash"
    assert "°C" in fig.layout.yaxis.title.text


def test_trend_line_is_coral_only_for_upward_trends():
    up = charts.trend_figure(*make(0.03), "x", "°C").data[1]
    down = charts.trend_figure(*make(-0.03), "x", "°C").data[1]
    assert up.line.color == charts.TREND_CORAL
    assert down.line.color == charts.TREND_NEUTRAL


def test_no_fitted_line_without_a_trend():
    annual, _ = make(0.03)
    short = annual.head(5)
    trend = calculate_linear_trend(short["year"], short["annual_mean"])
    assert len(charts.trend_figure(short, trend, "x", "°C").data) == 1


def test_comparison_figure_keeps_locations_distinct():
    a, ta = make(0.03, seed=1)
    b, tb = make(0.01, seed=9)
    fig = charts.comparison_figure([("A", a, ta), ("B", b, tb)], "x", "°C")
    assert len(fig.data) == 4
    assert fig.data[0].line.color != fig.data[2].line.color
    assert np.allclose(fig.data[2].y, b["annual_mean"])
    assert [t.name for t in fig.data if t.showlegend is not False] == ["A", "B"]
