"""Gamificação e cofrinho (specs/09).

O XP é **calculado a partir das transações**, não acumulado num contador. Isso
não é preguiça: contador incrementado por evento fica errado pra sempre no
primeiro erro, e aqui o dado de origem já existe. Apagar um lançamento corrige o
XP sozinho, em vez de deixar crédito fantasma.

Consequência: `user_progress` e `xp_events` seguem sem uso, como `accounts` — o
schema previa um desenho por evento e este é derivado. Não escrever neles é
deliberado; se o histórico crescer o bastante pra a conta pesar, o caminho é
materializar o mês fechado no `xp_events`, não voltar a incrementar contador.
"""

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.common import BUCKET_LABELS, money, month_bounds, to_decimal, today_local
from app.db import get_db
from app.gamification.rules import (
    RESULT_XP_POOL,
    XP_PER_ACTIVE_DAY,
    active_days_from,
    buckets_met,
    habit_xp,
    level_for,
    result_xp,
    roundup_of,
    xp_into_level,
)

# Conquistas. `code` é a chave estável; nome e descrição vivem aqui e não no
# banco porque são texto de produto, não dado do usuário — e assim não precisam
# de seed nem de migration pra mudar de redação.
ACHIEVEMENTS: tuple[dict, ...] = (
    {
        "code": "first_entry",
        "name": "Primeiro lançamento",
        "description": "Você registrou seu primeiro gasto.",
    },
    {
        "code": "active_7",
        "name": "Uma semana ativa",
        "description": "7 dias registrando no mesmo mês.",
    },
    {"code": "active_21", "name": "Virou hábito", "description": "21 dias ativos no mesmo mês."},
    {
        "code": "used_receipt",
        "name": "Foto de recibo",
        "description": "Você registrou um gasto pela foto do recibo.",
    },
    {
        "code": "used_import",
        "name": "Extrato importado",
        "description": "Você trouxe lançamentos do seu banco.",
    },
    {
        "code": "reserve_1",
        "name": "Um mês de colchão",
        "description": "Sua reserva cobre 1 mês do essencial.",
    },
    {
        "code": "reserve_3",
        "name": "Três meses de colchão",
        "description": "Sua reserva cobre 3 meses do essencial.",
    },
    {
        "code": "reserve_full",
        "name": "Reserva completa",
        "description": "Você chegou na meta da sua reserva.",
    },
    {
        "code": "month_perfect",
        "name": "Mês redondo",
        "description": "Você fechou um mês batendo os três buckets.",
    },
)


# --------------------------------------------------------------------------
# Progresso
# --------------------------------------------------------------------------


async def get_progress(current_user: CurrentUser) -> dict:
    month_start = today_local().replace(day=1)

    rows = await _month_rows(current_user, month_start)
    active_days = await _active_days(current_user, month_start)
    habit = habit_xp(active_days)

    rule = await targets_module.get_budget_rule(current_user.household_id)
    month_targets = await targets_module.ensure_month_targets(
        current_user.household_id, month_start
    )
    totals = targets_module.aggregate_month(rows)
    met = buckets_met(totals.by_bucket, month_targets)
    result = result_xp(met, rule)

    total = habit + result
    into, per_level = xp_into_level(total)

    return {
        "month": month_start.strftime("%Y-%m"),
        "level": level_for(total),
        "total_xp": total,
        "xp_into_level": into,
        "xp_per_level": per_level,
        # Dias ativos, não streak: sem quebra e sem punição (specs/10). Registrar
        # 30 lançamentos num dia conta como 1 — é o que impede o app de premiar
        # quem gasta mais.
        "active_days": active_days,
        "breakdown": [
            {
                "source": "habito",
                "label": "Dias ativos",
                "xp": habit,
                "detail": f"{active_days} × {XP_PER_ACTIVE_DAY} XP por dia registrado",
            },
            {
                "source": "resultado",
                "label": "Metas do mês",
                "xp": result,
                "detail": (
                    ", ".join(BUCKET_LABELS[bucket] for bucket in met)
                    if met
                    else "nenhum bucket fechado ainda"
                ),
            },
        ],
        # O mês em curso ainda pode ganhar o resto do pool. Dizer isso evita a
        # leitura de que o resultado "não conta".
        "result_xp_available": RESULT_XP_POOL,
        "month_in_progress": True,
    }


async def get_achievements(current_user: CurrentUser) -> dict:
    month_start = today_local().replace(day=1)
    rows = await _month_rows(current_user, month_start)
    unlocked = await _unlocked_codes(current_user, rows, month_start)

    return {
        "items": [
            {**achievement, "unlocked": achievement["code"] in unlocked}
            for achievement in ACHIEVEMENTS
        ],
        "unlocked_count": len(unlocked),
        "total": len(ACHIEVEMENTS),
    }


async def _unlocked_codes(
    current_user: CurrentUser, rows: list[dict], month_start: date
) -> set[str]:
    """Conquista é **derivada**, não gravada.

    Gravar exigiria um job pra destravar, e um job que falha deixa a conquista
    presa pra sempre. Derivando, ela aparece na primeira vez que a tela abre.
    O preço é não ter data de desbloqueio — `user_achievements` seguiria sendo o
    lugar disso, se algum dia importar.
    """
    codes: set[str] = set()

    if rows:
        codes.add("first_entry")

    methods = {row.get("entry_method") for row in rows}
    if "receipt_ocr" in methods:
        codes.add("used_receipt")
    if "csv_import" in methods:
        codes.add("used_import")

    active = await _active_days(current_user, month_start)
    if active >= 7:
        codes.add("active_7")
    if active >= 21:
        codes.add("active_21")

    # Conquista só precisa saber QUAIS buckets fecharam; o peso deles é assunto
    # do XP, então a regra do household não entra aqui.
    month_targets = await targets_module.ensure_month_targets(
        current_user.household_id, month_start
    )
    if len(buckets_met(targets_module.aggregate_month(rows).by_bucket, month_targets)) == 3:
        codes.add("month_perfect")

    reserve = await _reserve(current_user)
    if reserve:
        baseline = to_decimal(reserve["essential_expenses_baseline"])
        balance = to_decimal(reserve.get("current_balance") or 0)
        if baseline > 0:
            covered = balance / baseline
            if covered >= 1:
                codes.add("reserve_1")
            if covered >= 3:
                codes.add("reserve_3")
            if balance >= baseline * int(reserve["months_multiplier"]):
                codes.add("reserve_full")

    return codes


# --------------------------------------------------------------------------
# Cofrinho
# --------------------------------------------------------------------------


async def get_roundup(current_user: CurrentUser) -> dict:
    """Troco do arredondamento do mês.

    O potencial é **calculado das despesas**; o que já foi transferido vem do
    `roundup_savings`, que é o livro do que o usuário confirmou. Sem esse livro
    não haveria como distinguir "ainda tenho isso guardado" de "já transferi".
    """
    month_start = today_local().replace(day=1)
    rows = await _month_rows(current_user, month_start)

    per_transaction = {
        row["id"]: roundup_of(to_decimal(row["amount"]))
        for row in rows
        if row.get("type") == "expense"
    }

    transferred_ids = await _transferred_ids(current_user, list(per_transaction))
    accumulated = sum(
        (value for tx_id, value in per_transaction.items() if tx_id not in transferred_ids),
        Decimal("0"),
    )
    transferred = sum(
        (value for tx_id, value in per_transaction.items() if tx_id in transferred_ids),
        Decimal("0"),
    )

    return {
        "month": month_start.strftime("%Y-%m"),
        "accumulated": money(accumulated),
        "transferred": money(transferred),
        "eligible_transactions": len(per_transaction) - len(transferred_ids),
        # Manual nesta fase: o usuário confirma a transferência. Automação real
        # dependeria de ITP via Open Finance, que está adiado (ADR 0001) — e
        # prometer transferência automática que não acontece seria pior que nada.
        "automatic": False,
    }


async def transfer_roundup(current_user: CurrentUser) -> dict:
    month_start = today_local().replace(day=1)
    rows = await _month_rows(current_user, month_start)
    expense_ids = [row["id"] for row in rows if row.get("type") == "expense"]
    transferred_ids = await _transferred_ids(current_user, expense_ids)

    payload = []
    for row in rows:
        if row.get("type") != "expense" or row["id"] in transferred_ids:
            continue
        value = roundup_of(to_decimal(row["amount"]))
        if value <= 0:
            continue  # despesa em real inteiro não gera troco
        payload.append(
            {
                "user_id": current_user.user_id,
                "transaction_id": row["id"],
                "rounded_amount": str(value),
                "status": "transferred",
                "transferred_at": _now_iso(),
            }
        )

    if not payload:
        return {"transferred": "0.00", "count": 0}

    query = get_db().table("roundup_savings").insert(payload)
    result = await asyncio.to_thread(query.execute)
    created = result.data or []

    total = sum((to_decimal(row["rounded_amount"]) for row in payload), Decimal("0"))
    return {"transferred": money(total), "count": len(created)}


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------


async def _month_rows(current_user: CurrentUser, month_start: date) -> list[dict]:
    """Select próprio: precisa de `created_at` (dia ativo), `entry_method`
    (conquista) e `id` (cofrinho), que o de `targets` não traz — e do bucket
    embutido, que o `aggregate_month` usa."""
    start, end = month_bounds(month_start)
    query = (
        get_db()
        .table("transactions")
        .select(
            "id, amount, type, occurred_at, created_at, entry_method, category_id,"
            " categories(id, name, bucket, icon)"
        )
        .eq("household_id", current_user.household_id)
        .gte("occurred_at", start.isoformat())
        .lt("occurred_at", end.isoformat())
    )
    result = await asyncio.to_thread(query.execute)
    return result.data or []


async def _active_days(current_user: CurrentUser, month_start: date) -> int:
    """Dias em que o app foi **usado** no mês, por `created_at`.

    Consulta separada de `_month_rows` de propósito: aquela filtra por
    `occurred_at`, que é a data do gasto. Contar dia ativo dali erra nos dois
    sentidos — importar o extrato de julho no dia 20 de agosto não daria XP em
    agosto (o dia em que a pessoa de fato usou o app) e daria um dia ativo
    retroativo a julho, que já passou.
    """
    start, end = month_bounds(month_start)
    query = (
        get_db()
        .table("transactions")
        .select("created_at")
        .eq("household_id", current_user.household_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
    )
    result = await asyncio.to_thread(query.execute)
    return active_days_from([row.get("created_at") for row in (result.data or [])])


async def _transferred_ids(current_user: CurrentUser, transaction_ids: list[int]) -> set[int]:
    """Quais dos ids dados já foram transferidos.

    Limitado aos ids do mês: puxar o livro inteiro do usuário cresceria sem teto
    conforme o histórico, e a resposta só precisa do recorte consultado.
    """
    if not transaction_ids:
        return set()

    query = (
        get_db()
        .table("roundup_savings")
        .select("transaction_id")
        .eq("user_id", current_user.user_id)
        .eq("status", "transferred")
        .in_("transaction_id", transaction_ids)
    )
    result = await asyncio.to_thread(query.execute)
    return {row["transaction_id"] for row in (result.data or [])}


async def _reserve(current_user: CurrentUser) -> dict | None:
    query = (
        get_db()
        .table("emergency_reserve")
        .select("essential_expenses_baseline, current_balance, months_multiplier")
        .eq("household_id", current_user.household_id)
        .maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        return None
    return result.data


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
