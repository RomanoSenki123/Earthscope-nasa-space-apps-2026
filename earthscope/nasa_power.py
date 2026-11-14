"""Retrieval and parsing of NASA POWER monthly point data.

Endpoint: https://power.larc.nasa.gov/api/temporal/monthly/point
The response holds, per parameter, a mapping of ``YYYYMM`` keys to values.
POWER also includes a ``YYYY13`` key holding its own annual value; EarthScope
ignores it and recomputes annual means from the twelve monthly values so that
incomplete years can be detected.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd
import requests

from . import config

MONTHLY_COLUMNS = [
    "location", "latitude", "longitude", "parameter", "year", "month", "value", "unit",
]
_KEY_RE = re.compile(r"^\d{6}$")
_DEFAULT_FILL = -999.0


class PowerError(Exception):
    """A user-presentable problem obtaining or reading NASA POWER data."""


@dataclass
class MonthlyResult:
    """Cleaned monthly series plus the provenance needed to trace it."""

    data: pd.DataFrame  # MONTHLY_COLUMNS, valid values only, sorted by year/month
    location: str
    latitude: float
    longitude: float
    parameter: str
    unit: str
    longname: str
    start_year: int
    end_year: int
    fill_value: float
    sources: list[str] = field(default_factory=list)
    api_version: str = ""
    grid_point: tuple[float, ...] | None = None  # lon, lat, elevation reported by NASA
    request_url: str = ""
    accessed_utc: str = ""
    filtered: list[str] = field(default_factory=list)  # human-readable removed records
    warnings: list[str] = field(default_factory=list)


def validate_request(latitude: float, longitude: float, start_year: int, end_year: int) -> None:
    for name, value, low, high in (
        ("Latitude", latitude, -90.0, 90.0),
        ("Longitude", longitude, -180.0, 180.0),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise PowerError(f"{name} must be a finite number.")
        if not low <= value <= high:
            raise PowerError(f"{name} {value} is outside the valid range {low} to {high}.")
    for name, value in (("Start year", start_year), ("End year", end_year)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise PowerError(f"{name} must be a whole number.")
    latest = config.last_complete_year()
    if start_year < config.FIRST_AVAILABLE_YEAR:
        raise PowerError(f"NASA POWER monthly data begin in {config.FIRST_AVAILABLE_YEAR}.")
    if end_year > latest:
        raise PowerError(f"The last complete calendar year is {latest}; later years are not analyzed.")
    if start_year > end_year:
        raise PowerError("Start year must not be after end year.")


def fetch_power_payload(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    parameter: str = "T2M",
    *,
    session: requests.Session | None = None,
    sleep=time.sleep,
) -> tuple[dict, str]:
    """Request monthly data from NASA POWER. Returns ``(payload, request_url)``."""
    validate_request(latitude, longitude, start_year, end_year)
    params = {
        "parameters": parameter,
        "community": config.POWER_COMMUNITY,
        "latitude": latitude,
        "longitude": longitude,
        "start": start_year,
        "end": end_year,
        "format": "JSON",
    }
    http = session or requests
    last_problem = "unknown error"
    for attempt in range(config.REQUEST_RETRIES + 1):
        if attempt:
            sleep(1.5 * attempt)
        try:
            response = http.get(
                config.POWER_MONTHLY_URL, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
            )
        except requests.Timeout:
            last_problem = "the request timed out"
            continue
        except requests.RequestException as exc:
            last_problem = f"a network error occurred ({type(exc).__name__})"
            continue

        status = response.status_code
        if status == 429 or status >= 500:
            last_problem = f"the service returned HTTP {status}"
            continue
        if status != 200:
            raise PowerError(
                f"NASA POWER rejected the request (HTTP {status}). {_error_detail(response)}".strip()
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise PowerError("NASA POWER returned a response that is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise PowerError("NASA POWER returned JSON in an unexpected shape.")
        return payload, response.url

    raise PowerError(
        f"NASA POWER could not be reached after {config.REQUEST_RETRIES + 1} attempts: "
        f"{last_problem}. Please try again later."
    )


def _error_detail(response) -> str:
    """Pull a short message out of a POWER error body, if there is one."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        for key in ("messages", "message", "detail"):
            detail = body.get(key)
            if detail:
                return str(detail)[:300]
    return ""


def parse_power_monthly(
    payload: dict,
    parameter: str,
    location: str,
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
) -> MonthlyResult:
    """Validate a POWER monthly payload and turn it into a clean monthly table.

    Nothing is filled in or interpolated: fill values, non-numeric values and
    physically impossible values are dropped and listed in ``filtered``.
    """
    try:
        series = payload["properties"]["parameter"][parameter]
    except (KeyError, TypeError) as exc:
        raise PowerError(
            f"The NASA POWER response does not contain properties.parameter.{parameter}; "
            "the data cannot be read."
        ) from exc
    if not isinstance(series, dict):
        raise PowerError(f"The NASA POWER {parameter} series is not in the expected key/value form.")

    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    fill_value = header.get("fill_value", _DEFAULT_FILL)
    if isinstance(fill_value, bool) or not isinstance(fill_value, (int, float)):
        fill_value = _DEFAULT_FILL
    meta = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    meta = meta.get(parameter) if isinstance(meta.get(parameter), dict) else {}

    variable = config.VARIABLES.get(parameter)
    raw_unit = str(meta.get("units", "")).strip()
    unit = config.UNIT_DISPLAY.get(raw_unit, raw_unit) or (variable.unit if variable else "")
    warnings: list[str] = []
    if variable and raw_unit and unit != variable.unit:
        # The validity limits below are in the expected unit, so cleaning values in
        # another unit would wrongly discard them. Stop instead of guessing.
        raise PowerError(
            f"NASA reported units '{raw_unit}' for {parameter}, but EarthScope expects "
            f"{variable.unit}. The data were not analyzed."
        )

    rows: list[tuple[int, int, float]] = []
    filtered: list[str] = []
    for key, value in series.items():
        key = str(key).strip()
        if not _KEY_RE.match(key):
            filtered.append(f"{key}: not a YYYYMM key")
            continue
        year, month = int(key[:4]), int(key[4:])
        if month == 13:
            continue  # NASA's own annual aggregate; recomputed locally instead
        if not 1 <= month <= 12:
            filtered.append(f"{key}: invalid month")
            continue
        if not start_year <= year <= end_year:
            filtered.append(f"{key}: outside the requested years")
            continue
        label = f"{year}-{month:02d}"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            filtered.append(f"{label}: non-numeric value")
            continue
        value = float(value)
        if not math.isfinite(value):
            filtered.append(f"{label}: not a finite number")
            continue
        if value == fill_value or value == _DEFAULT_FILL:
            filtered.append(f"{label}: missing (NASA fill value)")
            continue
        if variable and not variable.valid_min <= value <= variable.valid_max:
            filtered.append(f"{label}: physically impossible value {value:g}")
            continue
        rows.append((year, month, value))

    frame = pd.DataFrame(rows, columns=["year", "month", "value"])
    duplicated = frame.duplicated(subset=["year", "month"], keep="first")
    if duplicated.any():
        warnings.append(
            f"{int(duplicated.sum())} duplicate year-month record(s) were found; the first was kept."
        )
        frame = frame[~duplicated]
    frame = frame.sort_values(["year", "month"]).reset_index(drop=True)
    frame["location"] = location
    frame["latitude"] = latitude
    frame["longitude"] = longitude
    frame["parameter"] = parameter
    frame["unit"] = unit
    frame = frame[MONTHLY_COLUMNS]

    api = header.get("api") if isinstance(header.get("api"), dict) else {}
    coords = None
    geometry = payload.get("geometry")
    if isinstance(geometry, dict) and isinstance(geometry.get("coordinates"), list):
        coords = tuple(geometry["coordinates"])

    return MonthlyResult(
        data=frame,
        location=location,
        latitude=latitude,
        longitude=longitude,
        parameter=parameter,
        unit=unit,
        longname=str(meta.get("longname", "")) or (variable.label if variable else parameter),
        start_year=start_year,
        end_year=end_year,
        fill_value=float(fill_value),
        sources=[str(s) for s in header.get("sources", [])] if isinstance(header.get("sources"), list) else [],
        api_version=str(api.get("version", "")),
        grid_point=coords,
        filtered=filtered,
        warnings=warnings,
    )


def fetch_power_monthly(
    location: str,
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    parameter: str = "T2M",
    *,
    session: requests.Session | None = None,
) -> MonthlyResult:
    """Fetch and clean one monthly series from NASA POWER."""
    payload, url = fetch_power_payload(
        latitude, longitude, start_year, end_year, parameter, session=session
    )
    result = parse_power_monthly(
        payload, parameter, location, latitude, longitude, start_year, end_year
    )
    result.request_url = url
    result.accessed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return result
