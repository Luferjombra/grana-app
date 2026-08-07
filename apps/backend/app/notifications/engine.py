"""Motor de alertas (specs/07).

Uma função só, chamada por dois gatilhos: o hook de evento (depois de salvar
uma transaction, dentro do FastAPI) e o cron diário (etl/projection_recompute).
Mesma regra nos dois caminhos — é o ponto da spec.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from postgrest.exceptions import APIError

from app.budget import targets as targets_module
from app.common import (
    BUCKET_LABELS,
    days_in_month,
    money,
    month_bounds,
    previous_month,
    today_local,
)
from app.db import get_db

logger = logging.getLogger(__name__)

# Código do Postgres pra violação de unique constraint.
UNIQUE_VIOLATION = "23505"

# Limiares fechados na spec 07.
CEILING_THRESHOLD = Decimal("0.95")
PROJECTION_THRESHOLD = Decimal("0.97")

# Antes disso a amostra é pequena demais: uma despesa fixa no dia 1 projetaria
# ~30x ela mesma e dispararia alerta de risco todo começo de mês. O alerta de
# teto não sofre disso (compara valor real), então só a projeção espera.
MIN_DAYS_FOR_PROJECTION = 7


@dataclass
class PendingNotification:
    type: str
    severity: str
    title: str
    message: str
    reference_month: date
    subject: str | None = None


def compute_projection(
    expense_so_far: Decimal, month_start: date, today: date
) -> tuple[Decimal, int] | None:
    """Projeção linear de fechamento. Retorna (projeção, dias_corridos) ou None
    quando ainda não dá pra projetar com confiança."""
    start, end = month_bounds(month_start)

    if today < start:
        return None  # mês futuro: nada gasto ainda
    days_elapsed = days_in_month(month_start) if today >= end else today.day

    if days_elapsed < MIN_DAYS_FOR_PROJECTION:
        return None

    daily_rate = expense_so_far / Decimal(days_elapsed)
    return (daily_rate * Decimal(days_in_month(month_start)), days_elapsed)


def _ceiling_notification(
    bucket: str, spent: Decimal, target: Decimal, month_start: date
) -> PendingNotification:
    pct = (spent / target * 100).quantize(Decimal("1"))
    label = BUCKET_LABELS[bucket]
    return PendingNotification(
        type="budget_ceiling",
        severity="warning",
        title=f"Você está perto do teto de {label}",
        message=(
            f"Já usou {pct}% do limite de {label} neste mês "
            f"(R$ {money(spent)} de R$ {money(target)})."
        ),
        reference_month=month_start,
        subject=bucket,
    )


def _projection_notification(
    projection: Decimal, income: Decimal, month_start: date
) -> PendingNotification:
    pct = (projection / income * 100).quantize(Decimal("1"))
    return PendingNotification(
        type="negative_projection",
        severity="danger",
        title="Projeção de fechamento em risco",
        message=(
            f"No ritmo atual, você deve fechar o mês gastando R$ {money(projection)} "
            f"({pct}% da renda)."
        ),
        reference_month=month_start,
    )


def _goal_hit_notification(
    bucket: str, spent: Decimal, target: Decimal, month_start: date
) -> PendingNotification:
    label = BUCKET_LABELS[bucket]
    return PendingNotification(
        type="goal_hit",
        severity="success",
        title=f"Meta batida em {label}",
        message=(
            f"Você fechou o mês dentro do teto de {label}: "
            f"R$ {money(spent)} de R$ {money(target)}."
        ),
        reference_month=month_start,
        subject=bucket,
    )


async def evaluate_month(
    household_id: int, month_start: date, today: date | None = None, closed: bool = False
) -> list[PendingNotification]:
    """Avalia as regras do mês e persiste as notificações resultantes.

    `closed=True` avalia um mês já encerrado — usado pelo cron do dia 1 pra
    gerar goal_hit do mês anterior, em vez dos alertas de risco (que não fazem
    sentido depois que o mês acabou).
    """
    today = today or today_local()

    rows = await targets_module.fetch_month_transactions(household_id, month_start)
    totals = targets_module.aggregate_month(rows)
    month_targets = await targets_module.ensure_month_targets(household_id, month_start)

    if not month_targets:
        # Sem renda cadastrada não há teto pra comparar — nada a alertar.
        return []

    pending: list[PendingNotification] = []

    if closed:
        for bucket, target in month_targets.items():
            spent = totals.by_bucket.get(bucket, Decimal("0"))
            if bucket == "poupanca":
                # Poupança é meta a atingir, não teto: "bateu" é chegar lá.
                if spent >= target:
                    pending.append(_goal_hit_notification(bucket, spent, target, month_start))
            elif Decimal("0") < spent <= target:
                # Exige gasto > 0: não dá pra distinguir "não gastou nada" de
                # "não registrou nada", e parabenizar quem passou o mês sem
                # abrir o app seria pior do que ficar calado.
                pending.append(_goal_hit_notification(bucket, spent, target, month_start))
    else:
        for bucket, target in month_targets.items():
            if bucket == "poupanca" or target <= 0:
                continue  # poupança é meta, não teto — não existe "estourar"
            spent = totals.by_bucket.get(bucket, Decimal("0"))
            if spent >= target * CEILING_THRESHOLD:
                pending.append(_ceiling_notification(bucket, spent, target, month_start))

        income = await targets_module.get_month_income(household_id, month_start)
        # Consumo, não saída total: aporte em poupança sair da conta é o plano
        # dando certo, não risco. Ver MonthTotals.consumption.
        projected = compute_projection(totals.consumption, month_start, today)
        if income > 0 and projected is not None:
            projection, _days = projected
            if projection > income * PROJECTION_THRESHOLD:
                pending.append(_projection_notification(projection, income, month_start))

    user_ids = await _household_member_ids(household_id)

    if not closed:
        # Reconcilia: alerta de risco que deixou de valer (usuário corrigiu o
        # valor, apagou a transação, aumentou o teto) tem que sair da lista —
        # senão fica um "já usou 98% do limite" não lido que virou mentira.
        still_valid = {(n.type, n.subject) for n in pending}
        await _dismiss_stale(user_ids, month_start, still_valid)

    for user_id in user_ids:
        for notification in pending:
            await _upsert_unread(user_id, notification)

    return pending


async def _household_member_ids(household_id: int) -> list[str]:
    """O orçamento é do household, então o alerta vai pra todos os membros —
    hoje sempre 1, mas a modelagem já é compartilhada."""
    return await targets_module.household_member_ids(household_id)


# Tipos que este caminho de avaliação é dono e pode retirar. goal_hit fica
# de fora: é registro de conquista, não um estado que deixa de valer.
RECONCILED_TYPES = ("budget_ceiling", "negative_projection")


async def _dismiss_stale(
    user_ids: list[str], month_start: date, still_valid: set[tuple[str, str | None]]
) -> None:
    """Apaga alertas de risco não lidos do mês que a reavaliação não reemitiu.

    Apaga em vez de marcar como lido: marcar como lido seria mentira (o
    usuário não leu), e um alerta que não vale mais é ruído, não histórico.
    """
    db = get_db()
    for user_id in user_ids:
        query = (
            db.table("notifications")
            .select("id, type, subject")
            .eq("user_id", user_id)
            .eq("reference_month", month_start.isoformat())
            .eq("read", False)
            .in_("type", list(RECONCILED_TYPES))
        )
        result = await asyncio.to_thread(query.execute)

        for row in result.data or []:
            if (row["type"], row["subject"]) in still_valid:
                continue
            delete_query = db.table("notifications").delete().eq("id", row["id"])
            await asyncio.to_thread(delete_query.execute)


async def _upsert_unread(user_id: str, notification: PendingNotification) -> None:
    """Atualiza o alerta não lido equivalente em vez de duplicar (specs/07).

    A migration 0003 tem um índice único parcial cobrindo essa mesma chave —
    ele é a rede de segurança contra a corrida entre este select e o insert
    (evento e cron podem avaliar o mesmo household ao mesmo tempo).
    """
    db = get_db()
    payload = {
        "severity": notification.severity,
        "title": notification.title,
        "message": notification.message,
    }
    key = {
        "user_id": user_id,
        "type": notification.type,
        "reference_month": notification.reference_month.isoformat(),
        "subject": notification.subject,
    }

    existing_query = (
        db.table("notifications")
        .select("id")
        .eq("user_id", user_id)
        .eq("type", notification.type)
        .eq("reference_month", key["reference_month"])
        .eq("read", False)
    )
    if notification.subject is None:
        existing_query = existing_query.is_("subject", "null")
    else:
        existing_query = existing_query.eq("subject", notification.subject)

    existing = await asyncio.to_thread(existing_query.execute)
    rows = existing.data or []

    if rows:
        update_query = db.table("notifications").update(payload).eq("id", rows[0]["id"])
        await asyncio.to_thread(update_query.execute)
        return

    insert_query = db.table("notifications").insert({**key, **payload, "read": False})
    try:
        await asyncio.to_thread(insert_query.execute)
    except APIError as exc:
        if exc.code != UNIQUE_VIOLATION:
            # Qualquer outra falha (migration 0003 não aplicada, permissão,
            # banco fora) precisa aparecer — engolir tudo aqui deixaria o
            # motor inteiro sem efeito sem nada nos logs.
            raise
        # Perdeu a corrida pro índice único: alguém já criou o mesmo alerta
        # não lido. Não é erro — é exatamente o que a idempotência quer.
        logger.info(
            "alerta %s/%s já existia para %s", notification.type, notification.subject, user_id
        )


async def evaluate_after_transaction(household_id: int, occurred_at: str) -> None:
    """Gatilho de evento: reavalia o mês da transação que acabou de mudar."""
    try:
        month_start = date.fromisoformat(occurred_at).replace(day=1)
    except ValueError:
        return

    try:
        await evaluate_month(household_id, month_start)
    except Exception:
        # Roda em background depois da resposta: falhar aqui não pode
        # derrubar nem reverter o registro da transação.
        logger.exception("falha ao avaliar alertas do household %s", household_id)


async def evaluate_daily(household_id: int, today: date | None = None) -> None:
    """Gatilho de cron: mês corrente sempre; no dia 1, fecha o mês anterior."""
    today = today or today_local()
    current_month = today.replace(day=1)

    await evaluate_month(household_id, current_month, today=today)

    if today.day == 1:
        await evaluate_month(household_id, previous_month(current_month), today=today, closed=True)
