"""Regression tests for issues raised in code review."""

import numpy as np
import pandas as pd
import pytest

from earthscope.explanations import describe_trend, format_pvalue
from earthscope.nasa_power import PowerError, parse_power_monthly
from earthscope.processing import annual_means
from earthscope.statistics import TrendResult, calculate_linear_trend


def _trend(slope):
    return TrendResult(
        ok=True, reason="", n=20, first_year=2000, last_year=2019, slope=slope, intercept=1.0,
        stderr=abs(slope), pvalue=0.4, r_squared=0.04, ci_low=-abs(slope) * 3, ci_high=abs(slope) * 3,
    )


@pytest.mark.parametrize("slope, word", [(0.00002, "increased"), (-0.00002, "decreased")])
def test_tiny_slope_keeps_its_direction(slope, word):
    text = describe_trend(_trend(slope), "Testville", "2-meter air temperature", "°C")
    assert word in text and "less than 0.001 °C per decade" in text
    assert "no net change" not in text


def test_exactly_zero_slope_is_no_net_change():
    text = describe_trend(_trend(0.0), "Testville", "2-meter air temperature", "°C")
    assert "no net change" in text


@pytest.mark.parametrize("p", [0.0499, 0.04996, 0.049999996, 0.0500004, 0.05004, 0.0504, 0.05 - 1e-14])
def test_displayed_pvalue_stays_on_its_side_of_the_threshold(p):
    text = format_pvalue(p)
    if text[0] in "<>":
        assert text == ("< 0.05" if p < 0.05 else "> 0.05")
    else:
        assert float(text) != 0.05 and (float(text) < 0.05) == (p < 0.05)


def test_exact_threshold_pvalue():
    assert format_pvalue(0.05) == "0.050"


def test_kelvin_payload_is_rejected_not_silently_filtered(payload_factory):
    payload = payload_factory({2000: [293.15] * 12}, units="K")
    with pytest.raises(PowerError, match="units 'K'"):
        parse_power_monthly(payload, "T2M", "Testville", 13.0, -59.0, 2000, 2000)


def test_annual_entry_cannot_complete_an_incomplete_year():
    series = {f"2000{m:02d}": 20.0 for m in range(1, 12)}  # 11 months
    series["200013"] = 20.0
    payload = {"properties": {"parameter": {"T2M": series}}, "parameters": {"T2M": {"units": "C"}}}
    data = parse_power_monthly(payload, "T2M", "Testville", 13.0, -59.0, 2000, 2000).data
    annual, dropped = annual_means(data, 2000, 2000)
    assert annual.empty and dropped == {2000: 11}


def test_aggregation_ignores_out_of_range_and_duplicate_months():
    rows = [("X", "T2M", 2000, m, 20.0, "°C") for m in range(1, 12)]
    rows += [("X", "T2M", 2000, 13, 20.0, "°C"), ("X", "T2M", 2000, 5, 20.0, "°C")]
    frame = pd.DataFrame(rows, columns=["location", "parameter", "year", "month", "value", "unit"])
    annual, dropped = annual_means(frame, 2000, 2000)
    assert annual.empty and dropped == {2000: 11}


def test_lag1_uses_only_consecutive_years():
    rng = np.random.default_rng(3)
    years = np.array([y for y in range(1990, 2020) if y not in (2000, 2001, 2010)], dtype=float)
    values = 0.02 * years + rng.normal(0, 0.2, years.size)
    trend = calculate_linear_trend(years, values)
    resid = values - trend.fitted(years)
    pairs = np.diff(years) == 1
    expected = np.sum((resid[1:] * resid[:-1])[pairs]) / np.sum(resid**2)
    assert trend.resid_lag1_autocorr == pytest.approx(expected)

    every_other = np.arange(1980, 2020, 2, dtype=float)
    gappy = calculate_linear_trend(every_other, 0.02 * every_other + rng.normal(0, 0.2, every_other.size))
    assert gappy.ok and gappy.resid_lag1_autocorr is None


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_non_finite_years_do_not_crash(bad):
    years = np.arange(2000, 2020, dtype=float)
    years[4] = bad
    trend = calculate_linear_trend(years, np.linspace(1, 2, years.size))
    assert not trend.ok and trend.first_year is None and trend.last_year is None
