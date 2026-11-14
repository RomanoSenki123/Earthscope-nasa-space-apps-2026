import numpy as np
import pytest
from scipy import stats

from earthscope.explanations import describe_trend, format_pvalue
from earthscope.statistics import calculate_linear_trend

YEARS = np.arange(2000, 2020)


def test_exact_linear_trend_recovers_slope():
    trend = calculate_linear_trend(YEARS, 10.0 + 0.03 * (YEARS - 2000))
    assert trend.ok and trend.n == 20
    assert trend.slope == pytest.approx(0.03)
    assert trend.slope_per_decade == pytest.approx(0.3)
    assert trend.r_squared == pytest.approx(1.0)
    assert trend.pvalue < 1e-10
    assert (trend.first_year, trend.last_year) == (2000, 2019)


def test_noisy_series_matches_scipy_and_ci_formula():
    rng = np.random.default_rng(42)
    values = 25 + 0.02 * (YEARS - 2000) + rng.normal(0, 0.2, YEARS.size)
    trend = calculate_linear_trend(YEARS, values)
    ref = stats.linregress(YEARS, values)
    tcrit = stats.t.ppf(0.975, YEARS.size - 2)
    assert trend.slope == pytest.approx(ref.slope)
    assert trend.pvalue == pytest.approx(ref.pvalue)
    assert trend.r_squared == pytest.approx(ref.rvalue**2)
    assert trend.ci_low == pytest.approx(ref.slope - tcrit * ref.stderr)
    assert trend.ci_high == pytest.approx(ref.slope + tcrit * ref.stderr)
    assert trend.ci_low < trend.slope < trend.ci_high
    assert -1 <= trend.resid_lag1_autocorr <= 1


def test_trendless_noise_is_not_significant():
    values = np.tile([1.0, -1.0], 10) + 20  # alternating, no drift
    trend = calculate_linear_trend(YEARS, values)
    assert trend.ok
    assert abs(trend.slope) < 0.02
    assert trend.pvalue > 0.05 and trend.significant is False


def test_constant_series_is_handled_safely():
    trend = calculate_linear_trend(YEARS, np.full(YEARS.size, 27.0))
    assert not trend.ok
    assert trend.slope == 0.0
    assert trend.pvalue is None and trend.significant is None
    assert "identical" in trend.reason


@pytest.mark.parametrize("n", [0, 1, 2, 9])
def test_too_few_observations_blocks_inference(n):
    trend = calculate_linear_trend(YEARS[:n], np.linspace(1, 2, n))
    assert not trend.ok and trend.n == n
    assert trend.pvalue is None and trend.significant is None


def test_non_finite_input_is_rejected():
    values = np.linspace(1, 2, YEARS.size)
    values[3] = np.nan
    assert not calculate_linear_trend(YEARS, values).ok


@pytest.mark.parametrize("slope, word", [(0.05, "increased"), (-0.05, "decreased")])
def test_result_text_follows_computed_slope(slope, word):
    rng = np.random.default_rng(1)
    values = 50 + slope * (YEARS - 2000) + rng.normal(0, 0.05, YEARS.size)
    trend = calculate_linear_trend(YEARS, values)
    text = describe_trend(trend, "Testville", "2-meter relative humidity", "%")
    assert word in text
    assert f"{abs(trend.slope_per_decade):.3f} % per decade" in text
    assert "Testville" in text and "2000–2019" in text and "20 complete years" in text
    assert "statistically significant at the 5% level" in text


def test_result_text_for_non_significant_and_insufficient():
    flat = calculate_linear_trend(YEARS, np.tile([1.0, -1.0], 10) + 20)
    text = describe_trend(flat, "Testville", "2-meter air temperature", "°C")
    assert "do not provide sufficient evidence" in text
    assert "proved" not in text

    short = calculate_linear_trend(YEARS[:5], [1, 2, 3, 4, 5])
    text = describe_trend(short, "Testville", "2-meter air temperature", "°C")
    assert "insufficient data for trend inference" in text.lower()
    assert "per decade" not in text


def test_pvalue_formatting_never_hides_which_side_of_threshold():
    assert format_pvalue(0.0004) == "< 0.001"
    assert format_pvalue(0.0312) == "0.031"
    assert format_pvalue(0.04996) == "0.04996"
    assert format_pvalue(0.05004) == "0.05004"
    assert format_pvalue(None) == "n/a"


def test_matches_independent_closed_form_ols():
    """Cross-check against textbook formulas computed without linregress."""
    rng = np.random.default_rng(7)
    x = np.arange(1991, 2026, dtype=float)
    y = 26.5 + 0.03 * (x - 1991) + rng.normal(0, 0.3, x.size)
    n = x.size
    sxx = np.sum((x - x.mean()) ** 2)
    slope = np.sum((x - x.mean()) * (y - y.mean())) / sxx
    intercept = y.mean() - slope * x.mean()
    resid = y - (intercept + slope * x)
    se = np.sqrt(np.sum(resid**2) / (n - 2) / sxx)
    p = 2 * stats.t.sf(abs(slope / se), n - 2)
    r2 = 1 - np.sum(resid**2) / np.sum((y - y.mean()) ** 2)
    half = stats.t.ppf(0.975, n - 2) * se

    trend = calculate_linear_trend(x, y)
    assert trend.slope == pytest.approx(slope)
    assert trend.intercept == pytest.approx(intercept)
    assert trend.stderr == pytest.approx(se)
    assert trend.pvalue == pytest.approx(p)
    assert trend.r_squared == pytest.approx(r2)
    assert (trend.ci_low, trend.ci_high) == pytest.approx((slope - half, slope + half))
    assert trend.ci_per_decade == pytest.approx(((slope - half) * 10, (slope + half) * 10))
