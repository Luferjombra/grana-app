from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.common import add_months, month_bounds, parse_month, split_installments


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


def test_add_months_keeps_the_day():
    assert add_months(date(2026, 8, 15), 3) == date(2026, 11, 15)


def test_add_months_rolls_over_the_year():
    assert add_months(date(2026, 11, 10), 3) == date(2027, 2, 10)


def test_add_months_clamps_to_the_last_day_of_a_short_month():
    """31 de janeiro + 1 mês não existe — cai no último dia de fevereiro,
    como faz a fatura de cartão."""
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_add_months_zero_is_the_same_date():
    assert add_months(date(2026, 8, 5), 0) == date(2026, 8, 5)


def test_add_months_twelve_lands_a_year_later():
    assert add_months(date(2026, 8, 31), 12) == date(2027, 8, 31)


def test_split_installments_divides_evenly():
    assert split_installments(Decimal("1200.00"), 12) == [Decimal("100.00")] * 12


def test_split_installments_always_sums_to_the_total():
    """Arredondar cada parcela por igual faria a soma não fechar com a compra."""
    for total, count in [("1000.00", 3), ("100.00", 7), ("0.05", 3), ("999.99", 11)]:
        parts = split_installments(Decimal(total), count)
        assert sum(parts) == Decimal(total), f"{total} em {count}x"
        assert len(parts) == count


def test_split_installments_puts_the_remainder_on_the_first():
    parts = split_installments(Decimal("1000.00"), 3)
    assert parts == [Decimal("333.34"), Decimal("333.33"), Decimal("333.33")]


def test_split_installments_single_returns_the_whole_amount():
    assert split_installments(Decimal("42.50"), 1) == [Decimal("42.50")]


def test_split_installments_rejects_zero():
    with pytest.raises(ValueError):
        split_installments(Decimal("10.00"), 0)
