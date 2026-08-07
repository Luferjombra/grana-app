from datetime import date

import pytest
from fastapi import HTTPException

from app.common import month_bounds, parse_month


def test_parse_month():
    assert parse_month("2026-08") == date(2026, 8, 1)


def test_parse_month_single_digit():
    assert parse_month("2026-1") == date(2026, 1, 1)


@pytest.mark.parametrize("value", ["", "2026", "2026-13", "agosto", "2026-08-05-01", None])
def test_parse_month_rejects_garbage(value):
    with pytest.raises(HTTPException) as exc_info:
        parse_month(value)
    assert exc_info.value.status_code == 422


def test_month_bounds_mid_year():
    start, end = month_bounds(date(2026, 8, 1))
    assert start == date(2026, 8, 1)
    assert end == date(2026, 9, 1)


def test_month_bounds_rolls_over_december():
    """Dezembro precisa virar janeiro do ano seguinte, não mês 13."""
    start, end = month_bounds(date(2026, 12, 1))
    assert start == date(2026, 12, 1)
    assert end == date(2027, 1, 1)


def test_month_bounds_february_leap_year():
    start, end = month_bounds(date(2028, 2, 1))
    assert end == date(2028, 3, 1)
