import asyncio
from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.common import money, parse_month, to_decimal, today_local
from app.db import get_db
from app.profile.schemas import RESERVE_MONTHS, IncomeCreate, OnboardingPayload


async def get_profile(current_user: CurrentUser) -> dict:
    query = (
        get_db()
        .table("profiles")
        .select("id, full_name, income_profile")
        .eq("id", current_user.user_id)
        .maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")

    current_month = today_local().replace(day=1)
    income = await targets_module.get_month_income(current_user.household_id, current_month)

    return {
        "full_name": result.data.get("full_name"),
        "income_profile": result.data.get("income_profile"),
        "current_income": money(income) if income > 0 else None,
        # O onboarding é pulável (specs/10) — este campo é o que a Home usa
        # pra decidir se mostra o card "informe sua renda".
        "onboarding_complete": income > 0,
    }


async def _reset_generated_targets(household_id: int, month_start: date) -> None:
    """Apaga os tetos do mês declarado **e dos seguintes** pra que sejam
    regerados com a renda nova.

    Do mês em diante, não só o mês: a renda declarada vale até uma declaração
    mais nova (specs/10), então qualquer mês posterior já materializado ficaria
    com o teto do salário antigo — e `ensure_month_targets` não sobrescreve o
    que já existe, então não se corrigiria sozinho.
    """
    query = (
        get_db()
        .table("budget_targets")
        .delete()
        .eq("household_id", household_id)
        .gte("month", month_start.isoformat())
    )
    await asyncio.to_thread(query.execute)


async def declare_income(
    current_user: CurrentUser, amount: Decimal, effective_month: date, source: str
) -> dict:
    """Declara "a partir deste mês, a renda é X" (specs/10). Meses seguintes
    herdam esse valor até uma declaração mais nova."""
    db = get_db()
    query = db.table("incomes").upsert(
        {
            "user_id": current_user.user_id,
            "amount": str(amount),
            "effective_month": effective_month.isoformat(),
            "source": source,
        },
        on_conflict="user_id,effective_month,source",
    )
    result = await asyncio.to_thread(query.execute)

    await _reset_generated_targets(current_user.household_id, effective_month)

    row = result.data[0] if result.data else {}
    return {**row, "amount": money(amount)}


async def create_income(current_user: CurrentUser, data: IncomeCreate) -> dict:
    effective_month = (
        parse_month(data.effective_month) if data.effective_month else today_local().replace(day=1)
    )
    return await declare_income(current_user, data.amount, effective_month, data.source)


async def list_incomes(current_user: CurrentUser) -> list[dict]:
    query = (
        get_db()
        .table("incomes")
        .select("id, amount, effective_month, source")
        .eq("user_id", current_user.user_id)
        .order("effective_month", desc=True)
    )
    result = await asyncio.to_thread(query.execute)
    return [{**row, "amount": money(to_decimal(row["amount"]))} for row in (result.data or [])]


async def complete_onboarding(current_user: CurrentUser, data: OnboardingPayload) -> dict:
    db = get_db()

    profile_query = (
        db.table("profiles")
        .update({"income_profile": data.income_profile})
        .eq("id", current_user.user_id)
    )
    await asyncio.to_thread(profile_query.execute)

    # A renda é gravada por último de propósito: `onboarding_complete` é
    # derivado dela, então se algum passo anterior falhar o usuário continua
    # marcado como pendente e o app o traz de volta pro fluxo. Na ordem
    # inversa, uma falha na reserva deixaria o onboarding "concluído" e a
    # reserva faltando pra sempre, sem caminho de retentativa.
    await _upsert_emergency_reserve(current_user, data)

    current_month = today_local().replace(day=1)
    await declare_income(current_user, data.monthly_income, current_month, "salario")

    return await get_profile(current_user)


async def _upsert_emergency_reserve(current_user: CurrentUser, data: OnboardingPayload) -> None:
    """Baseline estimado por renda × percentual de necessidades (specs/10):
    no dia 1 não existe histórico de gasto pra tirar a média real, e perguntar
    "quanto você gasta com o essencial?" é pergunta que o usuário não sabe
    responder. Passa a usar a média real quando o endpoint da reserva chegar.
    """
    rule = await targets_module.get_budget_rule(current_user.household_id)
    necessities_pct = to_decimal(rule["necessidades_pct"])
    baseline = (data.monthly_income * necessities_pct / Decimal("100")).quantize(Decimal("0.01"))

    query = (
        get_db()
        .table("emergency_reserve")
        .upsert(
            {
                "household_id": current_user.household_id,
                "profile": data.income_profile,
                "essential_expenses_baseline": str(baseline),
                "months_multiplier": RESERVE_MONTHS[data.income_profile],
            },
            on_conflict="household_id",
        )
    )
    await asyncio.to_thread(query.execute)
