from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from fastapi import HTTPException

BUCKETS = ("necessidades", "desejos", "poupanca")

BUCKET_LABELS = {
    "necessidades": "Necessidades",
    "desejos": "Desejos",
    "poupanca": "Poupança",
}

# O produto é brasileiro e o cron da spec 07 roda "meia-noite local" — datar
# pelo UTC do servidor jogaria transações das 21h–00h pro dia seguinte.
APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def today_local() -> date:
    return datetime.now(APP_TIMEZONE).date()


def previous_month(month_start: date) -> date:
    if month_start.month == 1:
        return date(month_start.year - 1, 12, 1)
    return date(month_start.year, month_start.month - 1, 1)


def days_in_month(month_start: date) -> int:
    _, end = month_bounds(month_start)
    return (end - month_start).days


def parse_month(month: str) -> date:
    """'2026-08' -> date(2026, 8, 1). O contrato da API (specs/09) usa sempre
    o formato YYYY-MM; no banco, month é o primeiro dia do mês."""
    try:
        year, month_number = month.split("-")
        return date(int(year), int(month_number), 1)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Mês inválido. Use o formato YYYY-MM.") from exc


def month_bounds(month_start: date) -> tuple[date, date]:
    """Primeiro dia do mês e primeiro dia do mês seguinte (intervalo semiaberto,
    pra filtrar occurred_at >= início e < fim sem depender de quantos dias tem)."""
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month


def to_decimal(value) -> Decimal:
    """Valores monetários trafegam como string decimal (specs/09) — nunca float,
    pra não acumular erro de arredondamento."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Valor monetário inválido.") from exc


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))
