"""Reserva de emergência (specs/09).

A reserva é `gasto essencial mensal × meses de colchão`. O multiplicador vem do
perfil de renda: 6 meses pra CLT, 12 pra autônomo, porque renda instável precisa
de mais folga (specs/10).

O baseline nasce **estimado** no onboarding (renda × percentual de necessidades),
porque no dia 1 não existe histórico de gasto e "quanto você gasta com o
essencial?" é pergunta que ninguém sabe responder. Aqui ele passa a ter uma
sugestão calculada do gasto real — mas a sugestão **não sobrescreve** o valor
guardado, no mesmo espírito de `ensure_month_targets` não sobrescrever target
manual: o usuário pode ter um motivo que o histórico não conhece.
"""

import asyncio
import logging
from decimal import Decimal

from fastapi import HTTPException

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.common import money, previous_month, to_decimal, today_local
from app.db import get_db
from app.notifications.engine import evaluate_reserve
from app.profile.schemas import RESERVE_MONTHS
from app.reserve.schemas import ReserveUpdate

logger = logging.getLogger(__name__)

# Meses olhados pra sugerir o baseline. Três é o mesmo horizonte do insight de
# média móvel: curto o bastante pra refletir a vida atual, longo o bastante pra
# não deixar um mês atípico ditar a meta.
BASELINE_MONTHS = 3

# Só sugere trocar o baseline quando a diferença é material. Abaixo disso a
# sugestão seria ruído e o usuário aprenderia a ignorar o aviso.
SUGGESTION_THRESHOLD = Decimal("0.10")


async def get_reserve(current_user: CurrentUser) -> dict:
    row = await _fetch(current_user.household_id)
    if row is None:
        # A reserva nasce no onboarding. Sem ela, o app precisa levar o usuário
        # de volta pra lá, não inventar um alvo do nada.
        raise HTTPException(
            status_code=404,
            detail="Reserva ainda não configurada. Complete o onboarding para definir sua meta.",
        )

    suggested = await _suggested_baseline(current_user.household_id)
    return _present(row, suggested)


async def update_reserve(current_user: CurrentUser, data: ReserveUpdate) -> dict:
    row = await _fetch(current_user.household_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Reserva ainda não configurada. Complete o onboarding para definir sua meta.",
        )

    changes: dict = {}
    if data.profile is not None:
        changes["profile"] = data.profile
        # O multiplicador acompanha o perfil: deixar os dois independentes
        # permitiria "autônomo com 6 meses", que não é uma escolha que a tela
        # oferece e viraria estado inconsistente sem ninguém notar.
        changes["months_multiplier"] = RESERVE_MONTHS[data.profile]
    if data.essential_expenses_baseline is not None:
        changes["essential_expenses_baseline"] = str(data.essential_expenses_baseline)
    if data.current_balance is not None:
        changes["current_balance"] = str(data.current_balance)

    query = (
        get_db()
        .table("emergency_reserve")
        .update(changes)
        .eq("household_id", current_user.household_id)
    )
    result = await asyncio.to_thread(query.execute)
    updated = (result.data or [row])[0]

    suggested = await _suggested_baseline(current_user.household_id)
    presented = _present(updated, suggested)

    # Marco da reserva é avaliado aqui, no evento, e não no cron diário: a
    # reserva só muda quando o usuário diz que mudou. Falha aqui não pode
    # derrubar o PATCH — o saldo já foi gravado, e perder o alerta é menos grave
    # que devolver erro num pedido que deu certo.
    try:
        await evaluate_reserve(
            current_user.household_id,
            to_decimal(presented["current_balance"]),
            to_decimal(presented["essential_expenses_baseline"]),
            to_decimal(presented["target"]),
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "falha ao avaliar marco da reserva do household %s", current_user.household_id
        )

    return presented


def _present(row: dict, suggested: Decimal | None) -> dict:
    baseline = to_decimal(row["essential_expenses_baseline"])
    multiplier = int(row["months_multiplier"])
    balance = to_decimal(row.get("current_balance") or 0)
    target = (baseline * multiplier).quantize(Decimal("0.01"))

    return {
        "profile": row["profile"],
        "essential_expenses_baseline": money(baseline),
        "months_multiplier": multiplier,
        "current_balance": money(balance),
        "target": money(target),
        "missing": money(max(target - balance, Decimal("0"))),
        # Percentual e meses cobertos são derivados, não guardados: qualquer
        # cópia no banco divergiria na primeira edição de baseline.
        "progress_pct": _pct(balance, target),
        "months_covered": _months_covered(balance, baseline),
        # `target > 0` não é redundante: com baseline zerado o alvo é zero, e
        # `balance >= target` diria "reserva completa" pra quem não tem nada
        # guardado. `_pct` e `_months_covered` já se protegem disso, e
        # `evaluate_reserve` também — este era o único sem guarda.
        "complete": target > 0 and balance >= target,
        "suggested_baseline": _suggestion(baseline, suggested),
    }


def _pct(balance: Decimal, target: Decimal) -> int:
    if target <= 0:
        return 0
    # Trava em 100: passar da meta é ótimo, mas barra de 140% confunde.
    return min(int((balance / target * 100).to_integral_value()), 100)


def _months_covered(balance: Decimal, baseline: Decimal) -> str | None:
    """Quantos meses de vida a reserva paga hoje. É o número que o usuário
    entende sem tradução — "3,5 meses" diz mais que "58%"."""
    if baseline <= 0:
        return None
    return str((balance / baseline).quantize(Decimal("0.1")))


def _suggestion(baseline: Decimal, suggested: Decimal | None) -> dict | None:
    """Só devolve sugestão quando há gasto real e a diferença é material.

    Devolver sempre faria a tela oferecer "atualizar para R$ 3.000,02" contra um
    baseline de R$ 3.000,00, e o usuário passaria a ignorar o aviso.
    """
    if suggested is None or suggested <= 0:
        return None

    difference = abs(suggested - baseline)
    if baseline > 0 and difference / baseline < SUGGESTION_THRESHOLD:
        return None

    return {
        "amount": money(suggested),
        "months_used": BASELINE_MONTHS,
        "direction": "up" if suggested > baseline else "down",
    }


async def _fetch(household_id: int) -> dict | None:
    query = (
        get_db()
        .table("emergency_reserve")
        .select("*")
        .eq("household_id", household_id)
        .maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        return None
    return result.data


async def _suggested_baseline(household_id: int) -> Decimal | None:
    """Média do gasto em **necessidades** nos meses fechados recentes.

    Usa só necessidades, não o gasto total: a reserva existe pra sustentar o
    essencial se a renda parar, e incluir desejos inflaria a meta pra um padrão
    de vida que ninguém mantém desempregado.

    Ignora o mês corrente, que está incompleto e puxaria a média pra baixo, e
    ignora mês sem gasto nenhum, que quase sempre significa "não registrei" e
    não "não gastei" — mesma leitura que o `goal_hit` da spec 07 faz.
    """
    month = previous_month(today_local().replace(day=1))
    values: list[Decimal] = []

    for _ in range(BASELINE_MONTHS):
        rows = await targets_module.fetch_month_transactions(household_id, month)
        totals = targets_module.aggregate_month(rows)
        essential = totals.by_bucket.get("necessidades", Decimal("0"))
        if essential > 0:
            values.append(essential)
        month = previous_month(month)

    if not values:
        return None
    return (sum(values) / len(values)).quantize(Decimal("0.01"))
