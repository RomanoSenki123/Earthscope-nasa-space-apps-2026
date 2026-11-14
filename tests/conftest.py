"""Shared SYNTHETIC fixtures. These values are invented for testing only and
are never shown by the app or presented as NASA data."""

import pytest


def make_payload(values_by_year, parameter="T2M", units="C"):
    """Build a payload shaped like a NASA POWER monthly response.

    ``values_by_year`` maps year -> list of 12 monthly values.
    """
    series = {}
    for year, months in values_by_year.items():
        for month, value in enumerate(months, start=1):
            series[f"{year}{month:02d}"] = value
        series[f"{year}13"] = 0.0  # POWER's annual entry; must be ignored
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-59.617, 13.098, 7.72]},
        "properties": {"parameter": {parameter: series}},
        "header": {
            "api": {"version": "test"},
            "sources": ["TEST-FIXTURE"],
            "fill_value": -999.0,
        },
        "parameters": {parameter: {"units": units, "longname": "Synthetic test series"}},
    }


@pytest.fixture
def payload_factory():
    return make_payload
