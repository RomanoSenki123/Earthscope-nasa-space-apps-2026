import pytest

from earthscope.nasa_power import parse_power_monthly
from earthscope.processing import ANNUAL_COLUMNS, annual_means


def monthly(payload, start, end):
    return parse_power_monthly(payload, "T2M", "Testville", 13.0, -59.0, start, end).data


def test_annual_mean_of_complete_years(payload_factory):
    data = monthly(payload_factory({2000: list(range(1, 13)), 2001: [10.0] * 12}), 2000, 2001)
    annual, dropped = annual_means(data, 2000, 2001)
    assert list(annual.columns) == ANNUAL_COLUMNS
    assert annual["year"].tolist() == [2000, 2001]
    assert annual["annual_mean"].tolist() == pytest.approx([6.5, 10.0])
    assert annual["valid_month_count"].tolist() == [12, 12]
    assert annual["unit"].unique().tolist() == ["°C"]
    assert dropped == {}


def test_year_with_fill_value_is_excluded_and_disclosed(payload_factory):
    bad = [20.0] * 12
    bad[2] = -999.0
    data = monthly(payload_factory({2000: [20.0] * 12, 2001: bad, 2002: [22.0] * 12}), 2000, 2002)
    annual, dropped = annual_means(data, 2000, 2002)
    assert annual["year"].tolist() == [2000, 2002]
    assert dropped == {2001: 11}


def test_year_missing_entirely_is_disclosed(payload_factory):
    data = monthly(payload_factory({2000: [20.0] * 12}), 2000, 2001)
    annual, dropped = annual_means(data, 2000, 2001)
    assert annual["year"].tolist() == [2000]
    assert dropped == {2001: 0}


def test_no_valid_data_gives_empty_table(payload_factory):
    data = monthly(payload_factory({2000: [-999.0] * 12}), 2000, 2000)
    annual, dropped = annual_means(data, 2000, 2000)
    assert annual.empty and list(annual.columns) == ANNUAL_COLUMNS
    assert dropped == {2000: 0}
