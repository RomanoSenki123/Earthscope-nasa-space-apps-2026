"""EarthScope — Ocean Observatory (Streamlit app).

Run with:  streamlit run app.py

This file is presentation only. Data retrieval, cleaning and statistics live in
the ``earthscope`` package; every number shown here comes from those results.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from earthscope import config
from earthscope.charts import comparison_figure, trend_figure
from earthscope.explanations import (
    AUDIENCES, GLOSSARY, LIMITATIONS, describe_agreement, describe_trend,
    explain_for_audience, format_pvalue, format_signed,
)
from earthscope.nasa_power import MonthlyResult, PowerError, fetch_power_monthly
from earthscope.processing import annual_means
from earthscope.statistics import (
    RobustTrend, TrendResult, calculate_linear_trend, calculate_robust_trend,
)

st.set_page_config(page_title="EarthScope | Ocean Observatory", page_icon="🌍", layout="wide")


@dataclass
class Analysis:
    monthly: MonthlyResult
    annual: pd.DataFrame
    dropped: dict[int, int]
    trend: TrendResult
    robust: RobustTrend


@st.cache_data(ttl=86400, show_spinner=False)
def load_monthly(name: str, lat: float, lon: float, start: int, end: int, parameter: str) -> MonthlyResult:
    """Cached for a day so normal interaction does not re-request NASA."""
    return fetch_power_monthly(name, lat, lon, start, end, parameter)


def analyze(loc: config.Location, start: int, end: int, parameter: str) -> Analysis:
    monthly = load_monthly(loc.name, loc.latitude, loc.longitude, start, end, parameter)
    annual, dropped = annual_means(monthly.data, start, end)
    trend = calculate_linear_trend(annual["year"], annual["annual_mean"])
    robust = calculate_robust_trend(annual["year"], annual["annual_mean"])
    return Analysis(monthly, annual, dropped, trend, robust)


def summary_row(a: Analysis) -> dict:
    t = a.trend
    r = a.robust
    ci = t.ci_per_decade if t.ok else None
    rci = r.sen_ci_per_decade if r.ok else None
    return {
        "location": a.monthly.location,
        "latitude": a.monthly.latitude,
        "longitude": a.monthly.longitude,
        "parameter": a.monthly.parameter,
        "unit": a.monthly.unit,
        "first_year": t.first_year,
        "last_year": t.last_year,
        "complete_years": t.n,
        "slope_per_year": t.slope if t.ok else None,
        "slope_per_decade": t.slope_per_decade if t.ok else None,
        "ci95_low_per_decade": ci[0] if ci else None,
        "ci95_high_per_decade": ci[1] if ci else None,
        "p_value": t.pvalue if t.ok else None,
        "r_squared": t.r_squared if t.ok else None,
        "significant_at_5pct": t.significant,
        "residual_lag1_autocorrelation": t.resid_lag1_autocorr if t.ok else None,
        "theil_sen_slope_per_decade": r.sen_slope_per_decade if r.ok else None,
        "theil_sen_ci95_low_per_decade": rci[0] if rci else None,
        "theil_sen_ci95_high_per_decade": rci[1] if rci else None,
        "mann_kendall_tau": r.mk_tau if r.ok else None,
        "mann_kendall_p_value": r.mk_pvalue if r.ok else None,
        "mann_kendall_significant_at_5pct": r.significant,
        "note": t.reason,
        "source": "NASA POWER monthly API (" + ", ".join(a.monthly.sources) + ")",
        "accessed_utc": a.monthly.accessed_utc,
        "request_url": a.monthly.request_url,
    }


# ---------------------------------------------------------------- UI helpers
def format_coord(lat: float, lon: float) -> str:
    return f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"


def kpi_card(column, label: str, value: str, note: str) -> None:
    """One summary card. Values wrap instead of being cut off."""
    with column.container(border=True, height="stretch"):
        st.caption(label)
        st.html(
            '<div style="font-size:1.45rem;font-weight:700;line-height:1.25;'
            f'overflow-wrap:anywhere;">{html.escape(value)}</div>'
        )
        st.caption(note)


def kpi_row(a: Analysis, rate_unit: str, requested_years: int) -> None:
    """Four cards: trend, period, confidence interval, significance."""
    t = a.trend
    cols = st.columns(4)
    if t.ok:
        low, high = t.ci_per_decade
        direction = "Upward" if t.slope > 0 else "Downward" if t.slope < 0 else "Flat"
        kpi_card(
            cols[0], "Estimated trend", f"{format_signed(t.slope_per_decade)} {rate_unit}/decade",
            f"{direction} · least-squares fit to annual means",
        )
        kpi_card(
            cols[2], "95% confidence interval",
            f"{format_signed(low)} to {format_signed(high)}",
            f"{rate_unit}/decade · statistical uncertainty of the fitted trend only",
        )
        p_text = format_pvalue(t.pvalue)
        kpi_card(
            cols[3], "Statistical significance",
            f"p {p_text}" if p_text[0] in "<>" else f"p = {p_text}",
            "Significant at the 5% level under the model's assumptions" if t.significant
            else "Not statistically significant at the 5% level",
        )
    else:
        kpi_card(cols[0], "Estimated trend", "N/A", "Insufficient data for trend inference")
        kpi_card(cols[2], "95% confidence interval", "N/A", "Not available")
        kpi_card(cols[3], "Statistical significance", "N/A", "Not available")
    span = f"{t.first_year}–{t.last_year}" if t.n else "no complete years"
    kpi_card(
        cols[1], "Period analyzed", f"{t.n} year{'s' if t.n != 1 else ''}",
        f"{span} · complete years only ({t.n} of {requested_years} requested have all 12 months)",
    )


def data_notes(a: Analysis) -> None:
    """Warnings, exclusions and the reason when no trend can be given."""
    for warning in a.monthly.warnings:
        st.warning(warning)
    if a.dropped:
        listed = ", ".join(f"{y} ({m}/12 months)" for y, m in sorted(a.dropped.items()))
        st.info(
            "Some years did not have all 12 valid monthly values and were excluded from "
            f"the trend analysis: {listed}."
        )
    if not a.trend.ok:
        st.warning(f"**Insufficient data for trend inference.** {a.trend.reason}")


def explainer(a: Analysis, variable_label: str, rate_unit: str, key: str) -> None:
    audience = st.segmented_control(
        "Reading level", AUDIENCES, default="General public", key=f"audience_{key}",
    ) or "General public"
    st.write(explain_for_audience(audience, a.trend, a.robust, a.monthly.location, variable_label, rate_unit))
    st.caption(
        "App-generated explanation: fixed wording filled with the computed results above. "
        "No AI model is involved."
    )


# ---------------------------------------------------------------- sidebar
latest_year = config.last_complete_year()
location_options = list(config.LOCATIONS) + [config.CUSTOM_LABEL]


def option_label(name: str) -> str:
    loc = config.LOCATIONS.get(name)
    return f"{name} (outside the Caribbean)" if loc and not loc.caribbean else name


with st.sidebar:
    st.markdown("## EarthScope")
    st.caption("OCEAN OBSERVATORY  \nAnalyze environmental change across the Caribbean.")
    with st.form("controls"):
        st.markdown("**Analysis settings**")
        location_name = st.selectbox(
            "Location", location_options,
            index=location_options.index(config.DEFAULT_LOCATION), format_func=option_label,
        )
        compare_options = ["None"] + location_options
        compare_name = st.selectbox(
            "Compare with (optional)", compare_options,
            index=compare_options.index(config.DEFAULT_COMPARISON), format_func=option_label,
        )
        with st.expander("Custom coordinates"):
            st.caption(f"Used only when “{config.CUSTOM_LABEL}” is selected above.")
            custom_lat = st.number_input(
                "Latitude (°, north positive)", -90.0, 90.0, config.DEFAULT_CUSTOM_POINT[0],
                step=0.5, format="%.4f",
            )
            custom_lon = st.number_input(
                "Longitude (°, east positive)", -180.0, 180.0, config.DEFAULT_CUSTOM_POINT[1],
                step=0.5, format="%.4f",
            )
        variable_key = st.selectbox(
            "Variable", list(config.VARIABLES),
            format_func=lambda k: f"{config.VARIABLES[k].label} ({config.VARIABLES[k].unit})",
        )
        start_year, end_year = st.slider(
            "Years", config.FIRST_AVAILABLE_YEAR, latest_year,
            (config.DEFAULT_START_YEAR, latest_year),
            help="Only fully completed calendar years can be selected.",
        )
        st.form_submit_button("Analyze trends", type="primary", width="stretch")


def resolve(name: str) -> config.Location:
    if name == config.CUSTOM_LABEL:
        lat, lon = round(custom_lat, 4), round(custom_lon, 4)
        return config.Location(f"Custom point ({lat:.4f}°, {lon:.4f}°)", lat, lon, caribbean=False)
    return config.LOCATIONS[name]


variable = config.VARIABLES[variable_key]
selected = [resolve(location_name)]
same_point_note = False
if compare_name != "None":
    other = resolve(compare_name)
    if (other.latitude, other.longitude) == (selected[0].latitude, selected[0].longitude):
        same_point_note = True
    else:
        selected.append(other)

# ---------------------------------------------------------------- header
context_line = f"{selected[0].name} · {variable.label} · {start_year}–{end_year}"
st.html(
    f"""
<div style="background:linear-gradient(110deg,#07142D 0%,#0B1736 55%,#123B5C 100%);
            color:#FFFFFF;border-radius:12px;padding:20px 26px;display:flex;flex-wrap:wrap;
            gap:10px 28px;align-items:flex-end;justify-content:space-between;
            border-left:6px solid #0893A3;">
  <div>
    <div style="font-size:0.78rem;letter-spacing:0.12em;text-transform:uppercase;color:#9FD8E0;">
      Ocean Observatory · Caribbean climate explorer</div>
    <h1 style="margin:2px 0 2px 0;padding:0;font-size:2.3rem;line-height:1.15;color:#FFFFFF;">EarthScope</h1>
    <div style="font-size:1.05rem;color:#E6EEF7;">Understand how our climate is changing.</div>
  </div>
  <div style="text-align:right;font-size:0.9rem;color:#E6EEF7;">
    <div style="font-weight:600;color:#FFFFFF;">{html.escape(context_line)}</div>
    <div>Data: NASA POWER · model-derived estimates</div>
  </div>
</div>
"""
)
st.caption(
    "Explore NASA model-derived environmental data, visualize long-term changes, and "
    "understand what the trends do, and do not, tell us."
)
if same_point_note:
    st.info("The comparison location is the same as the main location, so it is not shown twice.")

# ---------------------------------------------------------------- data
analyses: list[Analysis] = []
with st.spinner("Requesting data from NASA POWER…"):
    for loc in selected:
        try:
            analyses.append(analyze(loc, start_year, end_year, variable_key))
        except PowerError as exc:
            st.error(f"**{loc.name}:** {exc} Adjust the settings or press **Analyze trends** to retry.")
        except Exception:  # never show a stack trace to the user
            st.error(f"**{loc.name}:** an unexpected problem occurred while preparing the data.")

if not analyses:
    st.warning(
        "No NASA data could be loaded, so no results are shown. EarthScope never "
        "substitutes sample or estimated values for NASA data."
    )
    st.stop()

primary = analyses[0]
unit = primary.monthly.unit or variable.unit
rate_unit = variable.rate_unit  # unit used for rates of change
requested_years = end_year - start_year + 1
slug = "_".join(
    [re.sub(r"[^A-Za-z0-9]+", "-", primary.monthly.location).strip("-"), variable_key, f"{start_year}-{end_year}"]
)
annual_all = pd.concat([a.annual for a in analyses], ignore_index=True)
annual_csv = annual_all.to_csv(index=False).encode("utf-8-sig")
summary = pd.DataFrame([summary_row(a) for a in analyses])

# ---------------------------------------------------------------- main result
st.subheader(primary.monthly.location, anchor="results")
st.caption(
    f"{variable.label.capitalize()} (`{variable_key}`, {unit}) · requested {start_year}–{end_year} · "
    "a model-derived estimate for one grid cell, not a national, Caribbean-wide or global average."
)
kpi_row(primary, rate_unit, requested_years)
data_notes(primary)

if primary.annual.empty:
    st.warning(
        "No year in this range has all 12 valid monthly values, so there is nothing "
        "to plot or analyze. Try a different range."
    )
else:
    chart_col, context_col = st.columns([2.3, 1])
    with chart_col.container(border=True):
        st.markdown(f"**Annual mean {variable.label}**")
        st.caption(
            f"{primary.monthly.location} · {primary.trend.first_year}–{primary.trend.last_year} · "
            "model-derived annual values"
        )
        st.plotly_chart(
            trend_figure(primary.annual, primary.trend, variable.label, unit),
            width="stretch", theme=None,
        )
        st.caption(
            "Solid line: annual means computed from NASA POWER monthly values. Dashed line: "
            "least-squares fit over the analyzed years only; nothing is extrapolated. The "
            "vertical axis does not start at zero."
        )
    with context_col.container(border=True):
        m = primary.monthly
        st.markdown("**Location context**")
        st.caption("Model-derived grid cell, not a local thermometer.")
        st.markdown(f"**{m.location}**  \n{format_coord(m.latitude, m.longitude)}")
        st.map(
            pd.DataFrame({"lat": [m.latitude], "lon": [m.longitude]}),
            latitude="lat", longitude="lon", zoom=4, size=20000, color="#F28C52", height=230,
        )
        st.caption(
            "The marker shows the requested coordinates. Values describe the surrounding "
            "NASA model grid cell, roughly 50 km across; there is no sensor at this point."
        )
        st.caption(
            f"Source: NASA POWER ({', '.join(m.sources) or 'source not stated'}) · "
            f"retrieved {m.accessed_utc}"
        )

    with st.container(border=True):
        st.markdown("#### What does this mean?")
        explainer(primary, variable.label, rate_unit, "primary")

    with st.container(border=True):
        t, r = primary.trend, primary.robust
        st.markdown("**Statistical detail and robust check**")
        st.markdown(describe_trend(t, primary.monthly.location, variable.label, rate_unit))
        if t.ok and r.ok:
            r_low, r_high = r.sen_ci_per_decade
            rcols = st.columns(4)
            rcols[0].metric(
                f"Theil–Sen trend ({rate_unit}/decade)", format_signed(r.sen_slope_per_decade),
                help="A second estimate: the median of the slopes between every pair of years.",
            )
            rcols[1].metric(
                "Mann–Kendall p-value", format_pvalue(r.mk_pvalue),
                help="Tests for a consistent rise or fall without assuming a straight line.",
            )
            rcols[2].metric(
                "Kendall's τ", f"{r.mk_tau:.2f}",
                help="From −1 (always falling) to +1 (always rising); 0 means no consistent direction.",
            )
            rcols[3].metric(
                "R² (linear fit)", f"{t.r_squared:.2f}",
                help="Share of year-to-year variation described by the straight line.",
            )
            st.caption(
                f"95% CI for the Theil–Sen slope: {format_signed(r_low)} to {format_signed(r_high)} "
                f"{rate_unit}/decade. {describe_agreement(t, r)}"
            )

# ---------------------------------------------------------------- comparison
if len(analyses) > 1:
    st.subheader("Compare locations", anchor="compare")
    st.caption(
        f"Same variable ({variable.label}) and the same requested period ({start_year}–{end_year}) "
        "for both locations."
    )
    # Compare the exact years analyzed: the same span and count can still hide different gaps.
    coverage = {frozenset(a.annual["year"].astype(int)) for a in analyses}
    if len(coverage) > 1:
        st.warning(
            "The locations do not have the same complete years, so their trends cover "
            "different periods and are not directly comparable."
        )
    table = pd.DataFrame(
        {
            "Location": summary["location"],
            "Coverage": [
                f"{row.first_year}–{row.last_year} ({row.complete_years} yrs)" if row.complete_years else "none"
                for row in summary.itertuples()
            ],
            f"Trend ({rate_unit}/decade)": summary["slope_per_decade"].map(
                lambda v: format_signed(v) if pd.notna(v) else "n/a"
            ),
            f"95% CI ({rate_unit}/decade)": [
                f"{format_signed(row.ci95_low_per_decade)} to {format_signed(row.ci95_high_per_decade)}"
                if pd.notna(row.ci95_low_per_decade) else "n/a"
                for row in summary.itertuples()
            ],
            "p-value": [format_pvalue(p) if pd.notna(p) else "n/a" for p in summary["p_value"]],
            "R²": summary["r_squared"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "n/a"),
            "Significant at 5%": summary["significant_at_5pct"].map(
                {True: "Yes", False: "No"}
            ).fillna("n/a"),
            f"Theil–Sen ({rate_unit}/decade)": summary["theil_sen_slope_per_decade"].map(
                lambda v: format_signed(v) if pd.notna(v) else "n/a"
            ),
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")

    plotted = [(a.monthly.location, a.annual, a.trend) for a in analyses if not a.annual.empty]
    if len(plotted) > 1:
        with st.container(border=True):
            st.markdown(f"**Annual mean {variable.label}: both locations**")
            st.plotly_chart(comparison_figure(plotted, variable.label, unit), width="stretch", theme=None)
            st.caption(
                "Colour identifies the location. Solid lines are annual means; dashed lines "
                "are fitted trends."
            )
    st.caption(
        "Each location is fitted independently. These are sampled grid-cell values, "
        "not national or regional averages. EarthScope does not test whether the two "
        "slopes differ from each other. Comparing selected locations does not establish "
        "a Caribbean-wide average, and comparing with a single point outside the "
        "Caribbean does not show how the region compares with the world."
    )

    for index, other_analysis in enumerate(analyses[1:], start=1):
        with st.container(border=True):
            st.markdown(f"#### {other_analysis.monthly.location}")
            st.caption(format_coord(other_analysis.monthly.latitude, other_analysis.monthly.longitude))
            kpi_row(other_analysis, rate_unit, requested_years)
            data_notes(other_analysis)
            if not other_analysis.annual.empty:
                explainer(other_analysis, variable.label, rate_unit, f"compare_{index}")

# ---------------------------------------------------------------- downloads
st.subheader("Download the data", anchor="download")
left, right = st.columns(2)
left.download_button(
    "Download annual CSV", annual_csv, file_name=f"earthscope_annual_{slug}.csv",
    mime="text/csv", disabled=annual_all.empty, width="stretch",
)
right.download_button(
    "Download trend summary CSV", summary.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"earthscope_summary_{slug}.csv", mime="text/csv", width="stretch",
)
st.caption("The annual CSV holds exactly the values plotted above; the summary CSV holds every statistic shown.")

# ---------------------------------------------------------------- about / methods
st.subheader("About the data", anchor="about-the-data")
with st.expander("Data provenance"):
    for a in analyses:
        m = a.monthly
        st.markdown(f"**{m.location}** — requested point {m.latitude}, {m.longitude}")
        lines = [
            f"- Parameter: `{m.parameter}` — {m.longname} ({m.unit})",
            f"- Sources reported by NASA: {', '.join(m.sources) or 'not stated'}; API version {m.api_version or 'not stated'}",
            f"- Retrieved: {m.accessed_utc}",
            f"- Valid monthly values kept: {len(m.data)}; fill value: {m.fill_value:g}",
        ]
        if m.grid_point:
            lines.insert(1, f"- Point echoed by NASA (lon, lat, elevation m): {', '.join(str(c) for c in m.grid_point)}")
        st.markdown("\n".join(lines))
        st.markdown(f"- Request: {m.request_url}")
        if m.filtered:
            st.markdown("- Records removed: " + "; ".join(m.filtered[:50]) + (" …" if len(m.filtered) > 50 else ""))
        else:
            st.markdown("- Records removed: none")
    st.markdown(f"Documentation: [NASA POWER Monthly & Annual API]({config.POWER_DOCS_URL})")
    st.dataframe(annual_all, hide_index=True, width="stretch")

with st.expander("What do these terms mean?"):
    st.markdown("\n".join(f"- **{term}:** {meaning}" for term, meaning in GLOSSARY.items()))

st.subheader("Methods & limitations", anchor="methods")
with st.expander("How were these results calculated?"):
    st.markdown(
        f"""
1. Monthly `{variable_key}` values are requested from the NASA POWER monthly point API.
2. NASA's fill value (−999), non-numeric values and physically impossible values are removed. Nothing is interpolated or filled in.
3. An annual mean is the mean of the 12 monthly means, computed **only** for years with all 12 valid months. NASA's own annual entry (month `13`) is not used.
4. `scipy.stats.linregress` fits annual mean = intercept + slope × year. At least {config.MIN_YEARS_FOR_TREND} complete years are required.
5. Slope per decade = slope per year × 10. The 95% interval is slope ± t(0.975, n−2) × standard error. The p-value tests whether the slope differs from zero.
6. As a cross-check, the same annual values are also analyzed with the Theil–Sen slope (`scipy.stats.theilslopes`) and the Mann–Kendall test (computed as Kendall's tau between year and value, `scipy.stats.kendalltau`). These do not assume a straight line or normally distributed errors, but like least squares they assume the years are independent.
7. All figures shown come from the same annual table you can download.
"""
    )
    for a in analyses:
        if a.trend.ok and a.trend.resid_lag1_autocorr is not None:
            st.markdown(
                f"- {a.monthly.location}: lag-1 autocorrelation of residuals = "
                f"{a.trend.resid_lag1_autocorr:.2f} (diagnostic only; values far from 0 "
                "suggest the p-value and interval are optimistic)."
            )

with st.expander("Limitations and how to interpret this"):
    st.markdown("\n".join(f"- {item}" for item in LIMITATIONS))

with st.expander("AI assistance acknowledgment"):
    st.markdown(
        "Claude Code (Anthropic) assisted with software implementation, tests and "
        "documentation. All numbers shown are computed from NASA POWER records at "
        "run time; none are generated by an AI model. EarthScope is a NASA Space Apps "
        "Challenge 2026 project by team Bajan Chief and is not a NASA product or "
        "endorsed by NASA."
    )

st.divider()
st.caption(
    "EarthScope · Bajan Chief · NASA Space Apps Challenge 2026 · Independently developed "
    "participant project. Uses NASA POWER data; not affiliated with or endorsed by NASA."
)

# ---------------------------------------------------------------- sidebar (after results)
with st.sidebar:
    sections = ["[Results](#results)"]
    if len(analyses) > 1:
        sections.append("[Compare locations](#compare)")
    sections += ["[Download the data](#download)", "[About the data](#about-the-data)", "[Methods & limitations](#methods)"]
    st.markdown("**Sections**  \n" + "  \n".join(sections))
    st.markdown(
        f"**Data source**  \n[NASA POWER]({config.POWER_DOCS_URL})  \n"
        "MERRA-2 reanalysis (model), grid cells roughly 50 km across"
    )
    st.download_button(
        "Download annual CSV", annual_csv, file_name=f"earthscope_annual_{slug}.csv",
        mime="text/csv", disabled=annual_all.empty, width="stretch", key="sidebar_csv",
    )
    st.caption(
        "Preset points are approximate city coordinates used to pick a NASA model grid "
        "cell. They are not weather stations, and a result for one cell is not a "
        "national or regional average."
    )
