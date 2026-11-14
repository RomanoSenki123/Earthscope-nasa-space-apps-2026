"""Tests for the robust trend check and the audience explanations."""

import numpy as np
import pytest
from scipy import stats

from earthscope.explanations import AUDIENCES, GLOSSARY, describe_agreement, explain_for_audience
from earthscope.statistics import calculate_linear_trend, calculate_robust_trend

YEARS = np.arange(1991, 2026)


def series(slope, noise, seed=5):
    rng = np.random.default_rng(seed)
    return 27 + slope * (YEARS - 1991) + rng.normal(0, noise, YEARS.size)


def test_theil_sen_recovers_exact_slope_and_mk_is_certain():
    robust = calculate_robust_trend(YEARS, 10 + 0.03 * (YEARS - 1991))
    assert robust.ok
    assert robust.sen_slope == pytest.approx(0.03)
    assert robust.sen_slope_per_decade == pytest.approx(0.3)
    assert robust.mk_tau == pytest.approx(1.0)
    assert robust.significant is True


def test_theil_sen_is_median_of_pairwise_slopes():
    y = series(0.02, 0.3)
    pair_slopes = [(y[j] - y[i]) / (YEARS[j] - YEARS[i]) for i in range(len(y)) for j in range(i + 1, len(y))]
    robust = calculate_robust_trend(YEARS, y)
    assert robust.sen_slope == pytest.approx(np.median(pair_slopes))
    assert robust.sen_ci_low <= robust.sen_slope <= robust.sen_ci_high
    tau, p = stats.kendalltau(YEARS, y)
    assert (robust.mk_tau, robust.mk_pvalue) == pytest.approx((tau, p))


def test_outlier_moves_theil_sen_less_than_least_squares():
    y = 27 + 0.02 * (YEARS - 1991.0)
    y[-1] += 5.0
    ols = calculate_linear_trend(YEARS, y)
    robust = calculate_robust_trend(YEARS, y)
    assert abs(robust.sen_slope - 0.02) < abs(ols.slope - 0.02)
    assert robust.sen_slope == pytest.approx(0.02, abs=1e-3)


@pytest.mark.parametrize("values", [np.full(35, 27.0), np.r_[np.linspace(1, 2, 34), np.nan]])
def test_robust_handles_degenerate_series(values):
    robust = calculate_robust_trend(YEARS, values)
    assert not robust.ok and robust.significant is None and robust.sen_slope is None


def test_robust_needs_enough_years():
    assert not calculate_robust_trend(YEARS[:9], np.arange(9.0)).ok


def test_agreement_wording():
    strong = series(0.03, 0.1)
    both = describe_agreement(calculate_linear_trend(YEARS, strong), calculate_robust_trend(YEARS, strong))
    assert "Both methods find a statistically significant upward trend" in both

    flat = np.tile([1.0, -1.0, 0.5, -0.5, 0.0], 7) + 27 + 0.001 * (YEARS - 1991)
    neither = describe_agreement(calculate_linear_trend(YEARS, flat), calculate_robust_trend(YEARS, flat))
    # Trendless data: the methods may agree weakly or disagree, but never claim significance.
    assert "neither" in neither or "disagree on the direction" in neither
    assert "statistically significant upward" not in neither


@pytest.mark.parametrize("audience", AUDIENCES)
@pytest.mark.parametrize("slope", [0.03, -0.03])
def test_explanations_use_computed_numbers_and_direction(audience, slope):
    y = series(slope, 0.1)
    trend, robust = calculate_linear_trend(YEARS, y), calculate_robust_trend(YEARS, y)
    text = explain_for_audience(audience, trend, robust, "Testville", "2-meter air temperature", "°C")
    assert "Testville" in text and "1991" in text and "2025" in text
    if audience == "Scientist":
        assert f"{abs(trend.slope_per_decade):.3f}" in text and "Theil–Sen" in text and "Mann–Kendall" in text
    else:
        assert f"{abs(trend.slope_per_decade):.2f} °C" in text
        assert f"{abs(trend.slope * 34):.1f} °C" in text
        assert ("up" in text or "rising" in text) if slope > 0 else ("down" in text or "falling" in text)
    assert "model" in text.lower() or "reanalysis" in text.lower()
    for banned in ("proved", "caused by", "will rise", "forecast"):
        assert banned not in text


@pytest.mark.parametrize("audience", AUDIENCES)
def test_explanation_for_insufficient_data(audience):
    trend = calculate_linear_trend(YEARS[:5], [1, 2, 3, 4, 5])
    robust = calculate_robust_trend(YEARS[:5], [1, 2, 3, 4, 5])
    text = explain_for_audience(audience, trend, robust, "Testville", "2-meter air temperature", "°C")
    assert "not enough complete data" in text and "per decade" not in text


def test_non_significant_explanation_does_not_overclaim():
    y = np.tile([1.0, -1.0, 0.5, -0.5, 0.0], 7) + 27 + 0.001 * (YEARS - 1991)
    trend, robust = calculate_linear_trend(YEARS, y), calculate_robust_trend(YEARS, y)
    for audience in ("Student", "General public"):
        text = explain_for_audience(audience, trend, robust, "Testville", "2-meter air temperature", "°C")
        assert "could be chance" in text or "could be a chance pattern" in text
        assert "unlikely to be" not in text


def test_glossary_covers_displayed_terms():
    for term in ("p-value", "R²", "95% confidence interval", "Theil–Sen slope", "Mann–Kendall test"):
        assert term in GLOSSARY


# 35 values symmetric about the middle year: rises then falls, no net direction.
SYMMETRIC = 27.0 + np.abs(np.arange(35) - 17) * 0.125


def test_two_flat_slopes_count_as_agreement():
    trend = calculate_linear_trend(YEARS, SYMMETRIC)
    robust = calculate_robust_trend(YEARS, SYMMETRIC)
    assert trend.ok and robust.ok
    assert trend.slope == 0 and robust.sen_slope == 0
    text = describe_agreement(trend, robust)
    assert "disagree" not in text
    assert text == "Both methods find no fitted direction of change."


@pytest.mark.parametrize("audience", ["Student", "General public"])
def test_zero_fitted_change_is_described_neutrally(audience):
    trend = calculate_linear_trend(YEARS, SYMMETRIC)
    robust = calculate_robust_trend(YEARS, SYMMETRIC)
    text = explain_for_audience(audience, trend, robust, "Testville", "2-meter air temperature", "°C")
    assert "no net change" in text and "Testville" in text
    for word in ("falling", "rising", "goes down", "goes up", "disagree"):
        assert word not in text


def test_opposite_slopes_still_reported_as_disagreement():
    from earthscope.statistics import RobustTrend, TrendResult

    trend = TrendResult(True, "", 20, 2000, 2019, slope=0.01, intercept=1.0, stderr=0.01,
                        pvalue=0.3, r_squared=0.05, ci_low=-0.01, ci_high=0.03)
    for sen in (-0.01, 0.0):
        robust = RobustTrend(True, "", 20, sen, -0.02, 0.01, -0.05, 0.7)
        assert "disagree on the direction" in describe_agreement(trend, robust)
