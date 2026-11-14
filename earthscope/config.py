"""Static configuration: API settings, preset locations and supported variables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_DOCS_URL = "https://power.larc.nasa.gov/docs/services/api/temporal/monthly/"
POWER_METHODOLOGY_URL = "https://power.larc.nasa.gov/docs/methodology/data/processing/"
POWER_COMMUNITY = "SB"

REQUEST_TIMEOUT_SECONDS = 30
REQUEST_RETRIES = 2  # extra attempts after the first, for 429/5xx/network errors

# NASA POWER documents monthly meteorology from 1981 to the last completed year.
FIRST_AVAILABLE_YEAR = 1981
DEFAULT_START_YEAR = 1991

MIN_YEARS_FOR_TREND = 10
RECOMMENDED_YEARS_FOR_TREND = 20
SIGNIFICANCE_LEVEL = 0.05


def last_complete_year(today: date | None = None) -> int:
    """The most recent calendar year that has fully ended."""
    return (today or date.today()).year - 1


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    caribbean: bool = True


# Approximate city reference points used to select the NASA model grid cell.
# They are NOT weather-station coordinates.
LOCATIONS: dict[str, Location] = {
    loc.name: loc
    for loc in (
        Location("Bridgetown, Barbados", 13.0975, -59.6167),
        Location("Kingston, Jamaica", 17.9712, -76.7936),
        Location("Georgetown, Guyana", 6.8013, -58.1551),
        Location("Port of Spain, Trinidad and Tobago", 10.6549, -61.5019),
        # One reference point outside the region. A single city is not a global benchmark.
        Location("London, United Kingdom", 51.5074, -0.1278, caribbean=False),
    )
}
DEFAULT_LOCATION = "Bridgetown, Barbados"
DEFAULT_COMPARISON = "Kingston, Jamaica"
CUSTOM_LABEL = "Custom coordinates"
DEFAULT_CUSTOM_POINT = (25.0443, -77.3504)  # Nassau, The Bahamas (approximate)


@dataclass(frozen=True)
class Variable:
    key: str  # NASA POWER parameter name
    label: str
    unit: str  # display unit
    valid_min: float  # values outside [valid_min, valid_max] are physically impossible
    valid_max: float
    rate_unit: str  # unit for a rate of change (humidity changes are percentage points)


VARIABLES: dict[str, Variable] = {
    v.key: v
    for v in (
        Variable("T2M", "2-meter air temperature", "°C", -90.0, 60.0, "°C"),
        Variable("RH2M", "2-meter relative humidity", "%", 0.0, 100.0, "% points"),
    )
}
DEFAULT_VARIABLE = "T2M"

# NASA POWER reports units as plain ASCII; map them to display form.
UNIT_DISPLAY = {"C": "°C", "%": "%"}
