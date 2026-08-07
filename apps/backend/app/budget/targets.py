import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.common import BUCKETS, month_bounds, to_decimal
from app.db import get_db

DEFAULT_RULE = {"necessidades_pct": 50, "desejos_pct": 30, "poupanca_pct": 20}


@dataclass
class MonthTotals:
    income: Decimal
    expense: Decimal
    by_bucket: dict[str, Decimal]
    by_category: dict[int | None, dict]
    # Despesa cujo category_id ficou null (o schema faz `on delete set null`
    # quando a categoria é apagada). Não entra em bucket nenhum, então é
    # exposta à parte — do contrário a soma dos buckets não fecharia com o
    # total de gastos e o health score ignoraria o valor em silêncio.
    uncategorized_expense: Decimal


async def get_budget_rule(household_id: int) -> dict:
    query = (
        get_db().table("budget_rules").select("*").eq("household_id", household_id).maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        # O trigger de cadastro cria budget_rules junto com o household, mas
        # não dá pra assumir que sempre existe (household legado, trigger que
        # falhou) — cai no default 50-30-20 em vez de quebrar o dashboard.
        return dict(DEFAULT_RULE)
    return result.data


async def get_month_income(household_id: int, month_start: date) -> Decimal:
    """Renda do mês = soma de incomes de todos os membros do household.
    incomes é escopado por user_id, então precisa resolver os membros antes."""
    db = get_db()

    members_query = db.table("household_members").select("user_id").eq("household_id", household_id)
    members_result = await asyncio.to_thread(members_query.execute)
    user_ids = [row["user_id"] for row in (members_result.data or [])]
    if not user_ids:
        return Decimal("0")

    incomes_query = (
        db.table("incomes")
        .select("amount")
        .in_("user_id", user_ids)
        .eq("effective_month", month_start.isoformat())
    )
    incomes_result = await asyncio.to_thread(incomes_query.execute)

    return sum((to_decimal(row["amount"]) for row in (incomes_result.data or [])), Decimal("0"))


async def ensure_month_targets(household_id: int, month_start: date) -> dict[str, Decimal]:
    """Garante que budget_targets existe pro mês, derivando de renda × budget_rules.

    Compartilhado entre o dashboard e o motor de notificação (specs/07) —
    mesma regra, um lugar só. Não sobrescreve target já existente: o schema
    prevê override manual do teto.

    Retorna {} quando não há renda cadastrada pro mês (não dá pra derivar teto
    de renda zero) — o dashboard trata isso mostrando gasto sem barra de meta.
    """
    db = get_db()

    existing_query = (
        db.table("budget_targets")
        .select("bucket, target_amount")
        .eq("household_id", household_id)
        .eq("month", month_start.isoformat())
    )
    existing_result = await asyncio.to_thread(existing_query.execute)
    existing = {
        row["bucket"]: to_decimal(row["target_amount"]) for row in (existing_result.data or [])
    }

    if len(existing) == len(BUCKETS):
        return existing

    income = await get_month_income(household_id, month_start)
    if income <= 0:
        return existing

    rule = await get_budget_rule(household_id)
    missing = []
    for bucket in BUCKETS:
        if bucket in existing:
            continue
        pct = to_decimal(rule[f"{bucket}_pct"])
        amount = (income * pct / Decimal("100")).quantize(Decimal("0.01"))
        existing[bucket] = amount
        missing.append(
            {
                "household_id": household_id,
                "month": month_start.isoformat(),
                "bucket": bucket,
                "target_amount": str(amount),
            }
        )

    if missing:
        # on_conflict: outra request concorrente (ou o cron da spec 07) pode
        # ter criado o mesmo target no meio do caminho — não é erro.
        insert_query = db.table("budget_targets").upsert(
            missing, on_conflict="household_id,month,bucket", ignore_duplicates=True
        )
        await asyncio.to_thread(insert_query.execute)

    return existing


async def fetch_month_transactions(household_id: int, month_start: date) -> list[dict]:
    """Transações do mês com a categoria embutida — base tanto do dashboard
    quanto do motor de notificação (specs/07)."""
    start, end = month_bounds(month_start)

    query = (
        get_db()
        .table("transactions")
        .select("amount, type, category_id, categories(id, name, bucket, icon)")
        .eq("household_id", household_id)
        .gte("occurred_at", start.isoformat())
        .lt("occurred_at", end.isoformat())
    )
    result = await asyncio.to_thread(query.execute)
    return result.data or []


def aggregate_month(rows: Iterable[dict]) -> MonthTotals:
    """Agrega linhas já carregadas. Pura de propósito: o dashboard e o motor
    de notificação (specs/07) compartilham a regra sem repetir a query.

    'poupanca' soma despesas em categorias de poupança (aportar é uma saída
    da conta corrente) — lá é meta a atingir, não teto a respeitar.
    """
    totals = MonthTotals(
        income=Decimal("0"),
        expense=Decimal("0"),
        by_bucket={bucket: Decimal("0") for bucket in BUCKETS},
        by_category={},
        uncategorized_expense=Decimal("0"),
    )

    for row in rows:
        amount = to_decimal(row["amount"])

        if row["type"] == "income":
            totals.income += amount
            continue
        if row["type"] != "expense":
            continue

        totals.expense += amount

        category = row.get("categories") or {}
        bucket = category.get("bucket")
        if bucket in totals.by_bucket:
            totals.by_bucket[bucket] += amount
        else:
            totals.uncategorized_expense += amount

        category_id = row.get("category_id")
        entry = totals.by_category.setdefault(
            category_id,
            {
                "category_id": category_id,
                "name": category.get("name"),
                "bucket": bucket,
                "icon": category.get("icon"),
                "amount": Decimal("0"),
            },
        )
        entry["amount"] += amount

    return totals
