import pytest
import requests

from earthscope import nasa_power
from earthscope.nasa_power import PowerError, fetch_power_payload, parse_power_monthly

ARGS = ("Testville", 13.0, -59.0)


def parse(payload, start=2000, end=2001, parameter="T2M"):
    return parse_power_monthly(payload, parameter, *ARGS, start, end)


def test_happy_path_parses_all_months(payload_factory):
    result = parse(payload_factory({2000: [20.0] * 12, 2001: [21.0] * 12}))
    assert len(result.data) == 24
    assert list(result.data.columns) == nasa_power.MONTHLY_COLUMNS
    assert result.unit == "°C"
    assert result.sources == ["TEST-FIXTURE"]
    assert result.filtered == []
    assert result.data["year"].tolist() == sorted(result.data["year"].tolist())


def test_annual_key_13_is_ignored(payload_factory):
    result = parse(payload_factory({2000: [20.0] * 12}))
    assert set(result.data["month"]) == set(range(1, 13))
    assert 0.0 not in result.data["value"].values


def test_fill_value_is_removed_not_kept_as_temperature(payload_factory):
    months = [20.0] * 12
    months[5] = -999.0
    result = parse(payload_factory({2000: months}))
    assert len(result.data) == 11
    assert -999.0 not in result.data["value"].values
    assert any("2000-06" in item and "missing" in item for item in result.filtered)


@pytest.mark.parametrize("bad", [None, "25.1", float("nan"), float("inf"), True, 400.0])
def test_invalid_values_are_filtered(payload_factory, bad):
    months = [20.0] * 12
    months[0] = bad
    result = parse(payload_factory({2000: months}))
    assert len(result.data) == 11
    assert len(result.filtered) == 1


def test_malformed_keys_are_rejected(payload_factory):
    payload = payload_factory({2000: [20.0] * 12})
    series = payload["properties"]["parameter"]["T2M"]
    series.update({"2000": 1.0, "abc": 1.0, "200014": 1.0, "20000101": 1.0, "199912": 1.0})
    result = parse(payload)
    assert len(result.data) == 12
    assert len(result.filtered) == 5


def test_humidity_range_and_unit(payload_factory):
    months = [75.0] * 12
    months[3] = 130.0
    result = parse(payload_factory({2000: months}, parameter="RH2M", units="%"), parameter="RH2M")
    assert result.unit == "%"
    assert len(result.data) == 11


@pytest.mark.parametrize(
    "payload",
    [{}, {"properties": {}}, {"properties": {"parameter": {"RH2M": {}}}},
     {"properties": {"parameter": {"T2M": [1, 2]}}}, {"properties": None}],
)
def test_malformed_payload_raises_descriptive_error(payload):
    with pytest.raises(PowerError, match="T2M"):
        parse(payload)


@pytest.mark.parametrize(
    "lat, lon, start, end",
    [(91, 0, 2000, 2001), (0, 181, 2000, 2001), (float("nan"), 0, 2000, 2001),
     (0, 0, 1900, 2001), (0, 0, 2005, 2001), (0, 0, 2000, 3000), (0, 0, "2000", 2001)],
)
def test_invalid_request_arguments(lat, lon, start, end):
    with pytest.raises(PowerError):
        nasa_power.validate_request(lat, lon, start, end)


class FakeResponse:
    def __init__(self, status, body=None, text_only=False):
        self.status_code = status
        self._body = body
        self._text_only = text_only
        self.url = "https://example.invalid/test"

    def json(self):
        if self._text_only:
            raise ValueError("not json")
        return self._body


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        assert timeout
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def fetch(session):
    return fetch_power_payload(13.0, -59.0, 2000, 2001, session=session, sleep=lambda s: None)


def test_fetch_retries_transient_errors_then_succeeds(payload_factory):
    good = payload_factory({2000: [20.0] * 12})
    session = FakeSession([FakeResponse(503), requests.Timeout(), FakeResponse(200, good)])
    payload, url = fetch(session)
    assert payload is good and session.calls == 3


def test_fetch_gives_up_with_friendly_error():
    session = FakeSession([FakeResponse(500), FakeResponse(429), requests.ConnectionError()])
    with pytest.raises(PowerError, match="could not be reached"):
        fetch(session)


def test_fetch_does_not_retry_client_errors():
    session = FakeSession([FakeResponse(422, {"messages": ["bad parameter"]})])
    with pytest.raises(PowerError, match="422"):
        fetch(session)
    assert session.calls == 1


def test_fetch_rejects_non_json():
    with pytest.raises(PowerError, match="not valid JSON"):
        fetch(FakeSession([FakeResponse(200, text_only=True)]))
