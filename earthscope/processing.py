"""Annual aggregation of cleaned monthly data."""

from __future__ import annotations

import pandas as pd

ANNUAL_COLUMNS = ["location", "parameter", "year", "annual_mean", "unit", "valid_month_count"]


def annual_means(
    monthly: pd.DataFrame, start_year: int, end_year: int
) -> tuple[pd.DataFrame, dict[int, int]]:
    """Mean of the twelve monthly means, for complete years only.

    Returns ``(annual, dropped)`` where ``dropped`` maps every requested year
    that lacks 12 valid months to the number of valid months it did have.
    A partial year is never reported as a full-year mean.

    This is appropriate for mean-state variables such as temperature and
    relative humidity; it must not be reused for totals such as precipitation.
    """
    # Only distinct calendar months 1-12 count towards a complete year.
    monthly = monthly[monthly["month"].between(1, 12)].drop_duplicates(["year", "month"])
    counts = monthly.groupby("year")["value"].count() if len(monthly) else pd.Series(dtype=int)
    dropped = {
        year: int(counts.get(year, 0))
        for year in range(start_year, end_year + 1)
        if counts.get(year, 0) != 12
    }
    if monthly.empty:
        return pd.DataFrame(columns=ANNUAL_COLUMNS), dropped

    grouped = monthly.groupby("year").agg(
        annual_mean=("value", "mean"), valid_month_count=("value", "count")
    )
    complete = grouped[grouped["valid_month_count"] == 12].reset_index()
    first = monthly.iloc[0]
    complete["location"] = first["location"]
    complete["parameter"] = first["parameter"]
    complete["unit"] = first["unit"]
    complete = complete.sort_values("year").reset_index(drop=True)
    return complete[ANNUAL_COLUMNS], dropped
