"""EarthScope — Earth System Trend Detective (Streamlit app).

Run with:  streamlit run app.py
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from earthscope import config
from earthscope.charts import trend_figure
from earthscope.explanations import LIMITATIONS, describe_trend, format_pvalue, format_signed
from earthscope.nasa_power import MonthlyResult, PowerError, fetch_power_monthly
from earthscope.processing import annual_means
from earthscope.statistics import TrendResult, calculate_linear_trend

st.set_page_config(page_title="EarthScope", page_icon="🌍", layout="wide")


@dataclass
class Analysis:
    monthly: MonthlyResult
    annual: pd.DataFrame
    dropped: dict[int, int]
    trend: TrendResult


@st.cache_data(ttl=86400, show_spinner=False)
def load_monthly(name: str, lat: float, lon: float, start: int, end: int, parameter: str) -> MonthlyResult:
    """Cached for a day so normal interaction does not re-request NASA."""
    return fetch_power_monthly(name, lat, lon, start, end, parameter)


def analyze(loc: config.Location, start: int, end: int, parameter: str) -> Analysis:
    monthly = load_monthly(loc.name, loc.latitude, loc.longitude, start, end, parameter)
    annual, dropped = annual_means(monthly.data, start, end)
    trend = calculate_linear_trend(annual["year"], annual["annual_mean"])
    return Analysis(monthly, annual, dropped, trend)


def summary_row(a: Analysis) -> dict:
    t = a.trend
    ci = t.ci_per_decade if t.ok else None
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
        "note": t.reason,
        "source": "NASA POWER monthly API (" + ", ".join(a.monthly.sources) + ")",
        "accessed_utc": a.monthly.accessed_utc,
        "request_url": a.monthly.request_url,
    }


# ---------------------------------------------------------------- sidebar
latest_year = config.last_complete_year()
with st.sidebar.form("controls"):
    st.header("Investigation")
    location_options = list(config.LOCATIONS) + [config.CUSTOM_LABEL]

    def option_label(name: str) -> str:
        loc = config.LOCATIONS.get(name)
        return f"{name} (outside the Caribbean)" if loc and not loc.caribbean else name

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
    st.form_submit_button("Analyze", type="primary", width="stretch")
st.sidebar.caption(
    "EarthScope focuses on the Caribbean. Preset points are approximate city "
    "coordinates used to pick a NASA model grid cell. They are not weather stations, "
    "and a result for one cell is not a national or regional average."
)


def resolve(name: str) -> config.Location:
    if name == config.CUSTOM_LABEL:
        lat, lon = round(custom_lat, 4), round(custom_lon, 4)
        return config.Location(f"Custom point ({lat:.4f}°, {lon:.4f}°)", lat, lon, caribbean=False)
    return config.LOCATIONS[name]


variable = config.VARIABLES[variable_key]

# ---------------------------------------------------------------- header
st.title("EarthScope — Earth System Trend Detective")
st.write(
    "Investigate historical environmental change using NASA POWER data: what is "
    "changing, where, how fast, and whether the trend is statistically significant."
)

selected = [resolve(location_name)]
if compare_name != "None":
    other = resolve(compare_name)
    if (other.latitude, other.longitude) == (selected[0].latitude, selected[0].longitude):
        st.info("The comparison location is the same as the main location, so it is not shown twice.")
    else:
        selected.append(other)

analyses: list[Analysis] = []
with st.spinner("Requesting data from NASA POWER…"):
    for loc in selected:
        try:
            analyses.append(analyze(loc, start_year, end_year, variable_key))
        except PowerError as exc:
            st.error(f"**{loc.name}:** {exc}")
        except Exception:  # never show a stack trace to the user
            st.error(f"**{loc.name}:** an unexpected problem occurred while preparing the data.")

if not analyses:
    st.warning(
        "No NASA data could be loaded, so no results are shown. EarthScope never "
        "substitutes sample or estimated values for NASA data."
    )
    st.stop()

unit = analyses[0].monthly.unit or variable.unit
rate_unit = variable.rate_unit  # unit used for rates of change
st.caption(
    f"Source: NASA POWER monthly API / MERRA-2 reanalysis · {variable.label} "
    f"(`{variable_key}`, {unit}) · requested {start_year}–{end_year}  \n"
    "Every result below is a model-derived estimate for a single grid cell, not a "
    "national, Caribbean-wide or global average."
)

# ---------------------------------------------------------------- results
for a in analyses:
    t = a.trend
    st.subheader(a.monthly.location)
    for warning in a.monthly.warnings:
        st.warning(warning)
    if a.annual.empty:
        st.warning(
            "No year in this range has all 12 valid monthly values, so there is nothing "
            "to plot or analyze. Try a different range."
        )
        continue

    cols = st.columns(4)
    if t.ok:
        low, high = t.ci_per_decade
        cols[0].metric(
            f"Trend ({rate_unit}/decade)", format_signed(t.slope_per_decade),
            help=f"95% confidence interval: {format_signed(low)} to {format_signed(high)} {rate_unit}/decade",
        )
        cols[1].metric("p-value", format_pvalue(t.pvalue), help="Two-sided test of a zero slope.")
        cols[2].metric("R²", f"{t.r_squared:.2f}", help="Share of year-to-year variance described by the line.")
    else:
        cols[0].metric(f"Trend ({rate_unit}/decade)", "n/a")
        cols[1].metric("p-value", "n/a")
        cols[2].metric("R²", "n/a")
    cols[3].metric(
        "Complete years", f"{t.n} of {end_year - start_year + 1}",
        help=f"Coverage {t.first_year}–{t.last_year}. Years without 12 valid months are excluded.",
    )
    if t.ok:
        st.caption(
            f"95% CI for the slope: {format_signed(low)} to {format_signed(high)} {rate_unit}/decade "
            f"· coverage {t.first_year}–{t.last_year}"
        )
    st.markdown(describe_trend(t, a.monthly.location, variable.label, rate_unit))
    if a.dropped:
        listed = ", ".join(f"{y} ({m}/12 months)" for y, m in sorted(a.dropped.items()))
        st.info(f"Years excluded because they lack 12 valid monthly values: {listed}.")

plotted = [(a.monthly.location, a.annual, a.trend) for a in analyses if not a.annual.empty]
if plotted:
    st.subheader(f"Annual mean {variable.label}")
    st.plotly_chart(trend_figure(plotted, variable.label, unit), width="stretch")
    st.caption("Dashed lines are least-squares fits over the observed years only; nothing is extrapolated.")

summary = pd.DataFrame([summary_row(a) for a in analyses])
if len(analyses) > 1:
    st.subheader("Comparison")
    table = pd.DataFrame(
        {
            "Location": summary["location"],
            "Coverage": [
                f"{r.first_year}–{r.last_year} ({r.complete_years} yrs)" if r.complete_years else "none"
                for r in summary.itertuples()
            ],
            f"Trend ({rate_unit}/decade)": summary["slope_per_decade"].map(
                lambda v: format_signed(v) if pd.notna(v) else "n/a"
            ),
            f"95% CI ({rate_unit}/decade)": [
                f"{format_signed(r.ci95_low_per_decade)} to {format_signed(r.ci95_high_per_decade)}"
                if pd.notna(r.ci95_low_per_decade) else "n/a"
                for r in summary.itertuples()
            ],
            "p-value": [format_pvalue(p) if pd.notna(p) else "n/a" for p in summary["p_value"]],
            "R²": summary["r_squared"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "n/a"),
            "Significant at 5%": summary["significant_at_5pct"].map(
                {True: "Yes", False: "No"}
            ).fillna("n/a"),
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(
        "Each location is fitted independently. These are sampled grid-cell values, "
        "not national or regional averages. EarthScope does not test whether the two "
        "slopes differ from each other. Comparing with a single point outside the "
        "Caribbean does not show how the region compares with the world."
    )

# ---------------------------------------------------------------- downloads
st.subheader("Download")
annual_all = pd.concat([a.annual for a in analyses], ignore_index=True)
slug = f"{variable_key}_{start_year}-{end_year}"
left, right = st.columns(2)
left.download_button(
    "Download annual CSV", annual_all.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"earthscope_annual_{slug}.csv", mime="text/csv", disabled=annual_all.empty,
)
right.download_button(
    "Download summary CSV", summary.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"earthscope_summary_{slug}.csv", mime="text/csv",
)

# ---------------------------------------------------------------- expanders
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

with st.expander("How we computed the trend"):
    st.markdown(
        f"""
1. Monthly `{variable_key}` values are requested from the NASA POWER monthly point API.
2. NASA's fill value (−999), non-numeric values and physically impossible values are removed. Nothing is interpolated or filled in.
3. An annual mean is the mean of the 12 monthly means, computed **only** for years with all 12 valid months. NASA's own annual entry (month `13`) is not used.
4. `scipy.stats.linregress` fits annual mean = intercept + slope × year. At least {config.MIN_YEARS_FOR_TREND} complete years are required.
5. Slope per decade = slope per year × 10. The 95% interval is slope ± t(0.975, n−2) × standard error. The p-value tests whether the slope differs from zero.
6. All figures shown come from the same fit on the same annual table you can download.
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
