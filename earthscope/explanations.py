"""Plain-language wording built only from computed results."""

from __future__ import annotations

from . import config
from .statistics import RobustTrend, TrendResult

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


AUDIENCES = ["Student", "General public", "Scientist"]

GLOSSARY = {
    "Trend per decade": "How much the fitted straight line rises or falls every ten years.",
    "95% confidence interval": "A range of trend values that fit the data reasonably well. "
    "If the range does not include zero, the data point clearly in one direction.",
    "p-value": "How often a trend at least this strong would appear by chance if there were "
    "really no trend. Below 0.05 is conventionally called statistically significant. It is "
    "not the probability that the result is wrong.",
    "R²": "The share of the year-to-year variation that the straight line accounts for, "
    "from 0 (none) to 1 (all).",
    "Theil–Sen slope": "A second way to measure the trend: the middle value of the slopes "
    "between every pair of years. A few unusual years affect it much less.",
    "Mann–Kendall test": "A test of whether values tend to rise (or fall) over time, based "
    "only on their order. It does not assume the change follows a straight line.",
    "Grid cell": "The data come from a NASA weather model that divides the world into boxes "
    "roughly 50 km across. Each result describes one box, not a single town or thermometer.",
}


def describe_agreement(trend: TrendResult, robust: RobustTrend) -> str:
    """Say whether the two trend methods tell the same story."""
    if not trend.ok or not robust.ok:
        return ""
    # Classify each slope as falling (-1), flat (0) or rising (+1).
    ols_sign = (trend.slope > 0) - (trend.slope < 0)
    sen_sign = (robust.sen_slope > 0) - (robust.sen_slope < 0)
    if ols_sign == 0 and sen_sign == 0:
        return "Both methods find no fitted direction of change."
    if ols_sign != sen_sign:
        return (
            "The two methods disagree on the direction of change, so this series does "
            "not show a clear trend."
        )
    direction = "upward" if trend.slope > 0 else "downward"
    if trend.significant and robust.significant:
        return (
            f"Both methods find a statistically significant {direction} trend, which "
            "suggests the result is not driven by a few unusual years."
        )
    if not trend.significant and not robust.significant:
        return f"Both methods point {direction}, but neither finds the trend statistically significant."
    return (
        f"Both methods point {direction}, but only one finds the trend statistically "
        "significant. Treat this trend as uncertain."
    )


def explain_for_audience(
    audience: str, trend: TrendResult, robust: RobustTrend, location: str,
    variable_label: str, unit: str,
) -> str:
    """A fixed-template explanation of the computed results for a chosen reader.

    Written from the computed numbers only; no AI model is involved.
    """
    if not trend.ok:
        return (
            f"There is not enough complete data for {location} to estimate a trend. "
            f"{trend.reason}"
        )
    span = trend.last_year - trend.first_year
    per_decade = trend.slope_per_decade
    total = trend.slope * span
    low, high = trend.ci_per_decade
    rising = per_decade > 0
    agreement = describe_agreement(trend, robust)

    if audience == "Scientist":
        text = (
            f"OLS on {trend.n} complete annual means ({trend.first_year}–{trend.last_year}) for the "
            f"MERRA-2 grid cell containing {location}: slope {format_signed(per_decade)} {unit}/decade "
            f"(95% CI {format_signed(low)} to {format_signed(high)}), p {_p_phrase(trend.pvalue)}, "
            f"R² = {trend.r_squared:.2f}."
        )
        if robust.ok:
            r_low, r_high = robust.sen_ci_per_decade
            text += (
                f" Theil–Sen slope {format_signed(robust.sen_slope_per_decade)} {unit}/decade "
                f"(95% CI {format_signed(r_low)} to {format_signed(r_high)}); Mann–Kendall "
                f"τ = {robust.mk_tau:.2f}, p {_p_phrase(robust.mk_pvalue)}. {agreement}"
            )
        if trend.resid_lag1_autocorr is not None:
            text += (
                f" Lag-1 autocorrelation of the OLS residuals is {trend.resid_lag1_autocorr:.2f}; "
                "neither test corrects for serial correlation, so p-values and intervals may be "
                "optimistic."
            )
        return text + " Reanalysis grid-cell values are not station observations."

    if per_decade == 0:
        # A valid fit with exactly zero slope is neither rising nor falling.
        text = (
            f"NASA model data for the area around {location} show no net change in annual mean "
            f"{variable_label} on a fitted straight line between {trend.first_year} and "
            f"{trend.last_year}. Values go up and down from year to year, but the line through "
            "them is flat. "
        )
        if agreement:
            text += f"{agreement} "
        return text + (
            "These numbers come from a NASA computer model of the area, not from a thermometer "
            "in the town."
        )

    size = f"{abs(per_decade):.2f} {unit}"
    total_size = f"{abs(total):.1f} {unit}"
    if audience == "Student":
        text = (
            f"Imagine plotting one dot for each year's average {variable_label} near {location}, "
            f"then drawing the straight line that fits the dots best. That line goes "
            f"{'up' if rising else 'down'} by about {size} every ten years. Over the {span} years "
            f"from {trend.first_year} to {trend.last_year}, that adds up to about {total_size}. "
        )
        if trend.significant:
            text += (
                "Some years are higher and some are lower, but the overall "
                f"{'rise' if rising else 'fall'} is steady enough that it is unlikely to be just luck. "
            )
        else:
            text += (
                "But the dots jump around a lot from year to year, so this could be chance "
                "rather than a real change. "
            )
        if robust.ok:
            text += (
                "A second method, which is not easily fooled by one or two strange years, gives "
                f"{format_signed(robust.sen_slope_per_decade, 2)} {unit} every ten years. {agreement} "
            )
        return text + (
            "One thing to remember: these numbers come from a NASA computer model of the area, "
            "not from a thermometer in the town."
        )

    text = (
        f"NASA model data for the area around {location} show annual mean {variable_label} "
        f"{'rising' if rising else 'falling'} by about {size} per decade between {trend.first_year} "
        f"and {trend.last_year}, roughly {total_size} over the whole period. Values still go up and "
        f"down from year to year; the trend is the long-run direction underneath. The likely range "
        f"for the rate is {format_signed(low, 2)} to {format_signed(high, 2)} {unit} per decade. "
    )
    if trend.significant:
        text += "A change this consistent is unlikely to be a chance pattern. "
    else:
        text += "The year-to-year swings are large enough that this could be a chance pattern. "
    if robust.ok:
        text += (
            f"A second method that is less sensitive to unusual years gives "
            f"{format_signed(robust.sen_slope_per_decade, 2)} {unit} per decade. {agreement} "
        )
    return text + (
        "This describes one model grid cell about 50 km across, not the whole country, and it "
        "does not say what caused the change."
    )
