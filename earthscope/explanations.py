"""Plain-language wording built only from computed results."""

from __future__ import annotations

from . import config
from .statistics import TrendResult

LIMITATIONS = [
    "NASA POWER meteorological values come from the MERRA-2 reanalysis, a model that "
    "assimilates observations. They are not thermometer readings taken at the chosen point.",
    "A latitude/longitude selects a model grid cell (roughly 50 km across), so local "
    "microclimates, urban effects and station records may differ.",
    "A straight line can miss non-linear changes, steps and cycles.",
    "Year-to-year values are often serially correlated, which can make the standard "
    "error and p-value look more certain than they are.",
    "The chosen start and end years can materially change the estimated slope.",
    "Each result is an estimate for one sampled grid cell. It is not a national, "
    "Caribbean-wide or global average, and a handful of points cannot establish a "
    "regional warming rate.",
    "Comparing two points is not the same as comparing two countries, and comparing "
    "a Caribbean point with one city elsewhere does not show how the Caribbean "
    "compares with the world.",
    "Statistical significance is not practical importance, and a trend is not an "
    "explanation of its cause. A result that is not significant does not show that "
    "nothing changed.",
    "EarthScope describes the historical record only; it does not forecast.",
]


def format_pvalue(p: float | None) -> str:
    """Three decimals, or more when rounding would land exactly on the 0.05 threshold."""
    if p is None:
        return "n/a"
    if p < 0.001:
        return "< 0.001"
    alpha = config.SIGNIFICANCE_LEVEL
    for digits in range(3, 11):
        text = f"{p:.{digits}f}"
        # Rounding must not move the displayed value onto or across the threshold.
        if p == alpha or (float(text) < alpha) == (p < alpha) and float(text) != alpha:
            return text
    return f"< {alpha}" if p < alpha else f"> {alpha}"


def format_signed(value: float, digits: int = 3) -> str:
    text = f"{value:+.{digits}f}"
    return text.replace("-", "−") if float(text) != 0 else f"{0:.{digits}f}"


def describe_trend(trend: TrendResult, location: str, variable_label: str, unit: str) -> str:
    """One paragraph stating what the regression found, with its real numbers."""
    subject = f"For the NASA POWER grid cell containing **{location}**"
    if not trend.ok:
        return f"{subject}: **insufficient data for trend inference.** {trend.reason}"

    per_decade = trend.slope_per_decade
    low, high = trend.ci_per_decade
    # Direction follows the unrounded slope; only the displayed size is rounded.
    if per_decade == 0:
        change = f"annual mean {variable_label} showed no net change on a fitted straight line"
    else:
        direction = "increased" if per_decade > 0 else "decreased"
        size = "less than 0.001" if abs(per_decade) < 0.0005 else f"{abs(per_decade):.3f}"
        change = (
            f"annual mean {variable_label} {direction} by an estimated "
            f"**{size} {unit} per decade**"
        )
    if trend.significant:
        verdict = (
            "The estimated linear trend is statistically significant at the 5% level "
            "under this model's assumptions."
        )
    else:
        verdict = (
            "The data do not provide sufficient evidence of a nonzero linear trend at "
            "the 5% level under this model's assumptions. This is not evidence that "
            "nothing changed."
        )
    text = (
        f"{subject}, {change} over {trend.first_year}–{trend.last_year} "
        f"({trend.n} complete years; 95% confidence interval {format_signed(low)} to "
        f"{format_signed(high)} {unit} per decade; p {_p_phrase(trend.pvalue)}; "
        f"R² = {trend.r_squared:.2f}). {verdict}"
    )
    if trend.n < config.RECOMMENDED_YEARS_FOR_TREND:
        text += (
            f" With fewer than {config.RECOMMENDED_YEARS_FOR_TREND} years, treat this "
            "as a short-window estimate."
        )
    return text


def _p_phrase(p: float) -> str:
    text = format_pvalue(p)
    return text if text[0] in "<>" else f"= {text}"
