"""Ordinary least-squares linear trend on an annual series."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from . import config


@dataclass(frozen=True)
class TrendResult:
    ok: bool  # True when slope, p-value and interval are all usable
    reason: str  # why inference is unavailable when ok is False
    n: int
    first_year: int | None = None
    last_year: int | None = None
    slope: float | None = None  # units per year
    intercept: float | None = None
    stderr: float | None = None
    pvalue: float | None = None
    r_squared: float | None = None
    ci_low: float | None = None  # 95% CI for slope, units per year
    ci_high: float | None = None
    resid_lag1_autocorr: float | None = None  # diagnostic only

    @property
    def slope_per_decade(self) -> float | None:
        return None if self.slope is None else self.slope * 10

    @property
    def ci_per_decade(self) -> tuple[float, float] | None:
        if self.ci_low is None or self.ci_high is None:
            return None
        return self.ci_low * 10, self.ci_high * 10

    @property
    def significant(self) -> bool | None:
        if not self.ok or self.pvalue is None:
            return None
        return self.pvalue < config.SIGNIFICANCE_LEVEL

    def fitted(self, years) -> np.ndarray:
        return self.intercept + self.slope * np.asarray(years, dtype=float)


def calculate_linear_trend(years, values, min_years: int = config.MIN_YEARS_FOR_TREND) -> TrendResult:
    """Fit ``value = intercept + slope * year`` with ``scipy.stats.linregress``.

    The p-value is the two-sided test of slope = 0 and the 95% interval is
    ``slope ± t(0.975, n-2) * stderr``; both assume independent, normally
    distributed residuals.
    """
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        return TrendResult(False, "Years and values do not line up.", n=0)
    n = int(x.size)
    if n == 0:
        return TrendResult(False, "There are no complete years to analyze.", n=0)
    if not np.isfinite(x).all():
        return TrendResult(False, "The annual series contains invalid years.", n)
    first, last = int(x.min()), int(x.max())
    if not np.isfinite(y).all():
        return TrendResult(False, "The annual series contains non-numeric values.", n, first, last)
    if n < min_years:
        return TrendResult(
            False,
            f"Only {n} complete year(s) are available; at least {min_years} are needed "
            "for a trend estimate.",
            n, first, last,
        )
    if np.unique(x).size < 2:
        return TrendResult(False, "All observations fall in the same year.", n, first, last)
    if np.ptp(y) == 0:
        return TrendResult(
            False,
            "Every annual value is identical, so the slope is zero and its uncertainty "
            "cannot be estimated.",
            n, first, last, slope=0.0, intercept=float(y[0]),
        )

    fit = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, n - 2)
    numbers = (fit.slope, fit.intercept, fit.stderr, fit.pvalue, fit.rvalue, tcrit)
    if not all(math.isfinite(v) for v in numbers):
        return TrendResult(False, "The regression did not produce finite results.", n, first, last)

    order = np.argsort(x)
    resid = (y - (fit.intercept + fit.slope * x))[order]
    denom = float(np.sum(resid**2))
    # Only pairs of consecutive years are lag-1 pairs; excluded years leave gaps.
    consecutive = np.diff(x[order]) == 1
    lag1 = None
    if denom > 0 and consecutive.any():
        lag1 = float(np.sum((resid[1:] * resid[:-1])[consecutive]) / denom)

    return TrendResult(
        ok=True,
        reason="",
        n=n,
        first_year=first,
        last_year=last,
        slope=float(fit.slope),
        intercept=float(fit.intercept),
        stderr=float(fit.stderr),
        pvalue=float(fit.pvalue),
        r_squared=float(fit.rvalue**2),
        ci_low=float(fit.slope - tcrit * fit.stderr),
        ci_high=float(fit.slope + tcrit * fit.stderr),
        resid_lag1_autocorr=lag1,
    )


@dataclass(frozen=True)
class RobustTrend:
    """Rank-based cross-check of the least-squares trend."""

    ok: bool
    reason: str
    n: int
    sen_slope: float | None = None  # Theil-Sen slope, units per year
    sen_ci_low: float | None = None  # 95% CI, units per year
    sen_ci_high: float | None = None
    mk_tau: float | None = None  # Kendall's tau between year and value
    mk_pvalue: float | None = None  # Mann-Kendall test of no monotonic trend

    @property
    def sen_slope_per_decade(self) -> float | None:
        return None if self.sen_slope is None else self.sen_slope * 10

    @property
    def sen_ci_per_decade(self) -> tuple[float, float] | None:
        if self.sen_ci_low is None or self.sen_ci_high is None:
            return None
        return self.sen_ci_low * 10, self.sen_ci_high * 10

    @property
    def significant(self) -> bool | None:
        if not self.ok or self.mk_pvalue is None:
            return None
        return self.mk_pvalue < config.SIGNIFICANCE_LEVEL


def calculate_robust_trend(years, values, min_years: int = config.MIN_YEARS_FOR_TREND) -> RobustTrend:
    """Theil-Sen slope and Mann-Kendall test for the same annual series.

    The Theil-Sen slope is the median of the slopes between every pair of years,
    so a few unusual years move it far less than they move a least-squares line.
    The Mann-Kendall test is computed as Kendall's tau between year and value
    (``scipy.stats.kendalltau``); it asks whether values tend to rise or fall
    over time without assuming a straight line or normally distributed errors.
    Like least squares, it still assumes the years are independent.
    """
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        return RobustTrend(False, "Years and values do not line up.", n=0)
    n = int(x.size)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        return RobustTrend(False, "The annual series contains invalid values.", n)
    if n < min_years:
        return RobustTrend(False, f"Only {n} complete year(s) are available; at least {min_years} are needed.", n)
    if np.unique(x).size < 2 or np.ptp(y) == 0:
        return RobustTrend(False, "The series does not vary, so a rank-based test is undefined.", n)

    slope, _intercept, low, high = stats.theilslopes(y, x, alpha=0.95)
    tau, pvalue = stats.kendalltau(x, y)
    if not all(math.isfinite(v) for v in (slope, low, high, tau, pvalue)):
        return RobustTrend(False, "The robust estimate did not produce finite results.", n)
    return RobustTrend(True, "", n, float(slope), float(low), float(high), float(tau), float(pvalue))
