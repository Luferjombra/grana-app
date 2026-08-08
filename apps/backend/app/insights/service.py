"""Insights (specs/09).

Cinco leituras sobre os mesmos dados de transação. O que elas têm em comum é uma
armadilha: quase toda comparação envolvendo o **mês corrente** mente por
omissão, porque o mês está incompleto. Cada função aqui trata isso de forma
explícita, em vez de devolver um número bonito e errado.

Aporte em poupança é excluído do "gasto" em todos os insights, pelo mesmo motivo
da spec 07: investir é a saída planejada dando certo, não consumo. Somar os dois
faria quem cumpre o 50-30-20 parecer gastador. Ver `MonthTotals.consumption`.
"""

import asyncio
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.budget.health import compute_health_score
from app.common import (
    BUCKET_LABELS,
    BUCKETS,
    add_months,
    money,
    month_bounds,
    previous_month,
    to_decimal,
    today_local,
)
from app.db import get_db
from app.imports.suggest import merchant_key

# Janela olhada pra detectar assinatura. Seis meses cobre quem entrou no app
# recentemente e ainda dá margem pra ver repetição de verdade.
SUBSCRIPTION_WINDOW_MONTHS = 6

# Mínimo de meses distintos pra chamar de assinatura. Com 2 seria "comprei duas
# vezes"; 3 é o primeiro número em que "todo mês" começa a ser uma afirmação.
MIN_MONTHS_FOR_SUBSCRIPTION = 3

# Tolerância no valor: assinatura reajusta e cobrança em dólar varia com o
# câmbio. 15% aceita isso sem confundir dois gastos diferentes no mesmo lugar.
SUBSCRIPTION_AMOUNT_TOLERANCE = Decimal("0.15")

AVERAGE_MONTHS = 3
DEFAULT_TOP_LIMIT = 5
MAX_TOP_LIMIT = 50


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------


async def _fetch_range(household_id: int, start: date, end: date) -> list[dict]:
    """Transações no intervalo semiaberto [start, end).

    Select próprio, mais largo que o de `targets.fetch_month_transactions`:
    insight precisa de `occurred_at` (pra comparar dia a dia e datar o top) e de
    `merchant` (pra detectar assinatura), que aquele não traz.
    """
    query = (
        get_db()
        .table("transactions")
        .select(
            "id, amount, type, occurred_at, merchant, category_id,"
            " categories(id, name, bucket, icon)"
        )
        .eq("household_id", household_id)
        .gte("occurred_at", start.isoformat())
        .lt("occurred_at", end.isoformat())
    )
    result = await asyncio.to_thread(query.execute)
    return result.data or []


def _expenses(rows: list[dict], include_savings: bool = False) -> list[dict]:
    """Só despesa, e por padrão **sem** aporte em poupança."""
    out = []
    for row in rows:
        if row.get("type") != "expense":
            continue
        if not include_savings and (row.get("categories") or {}).get("bucket") == "poupanca":
            continue
        out.append(row)
    return out


def _sum(rows: list[dict]) -> Decimal:
    return sum((to_decimal(row["amount"]) for row in rows), Decimal("0"))


def _by_bucket(rows: list[dict]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {bucket: Decimal("0") for bucket in BUCKETS}
    for row in rows:
        bucket = (row.get("categories") or {}).get("bucket")
        if bucket in totals:
            totals[bucket] += to_decimal(row["amount"])
    return totals


def _delta(current: Decimal, previous: Decimal) -> dict:
    """Variação absoluta e percentual.

    `delta_pct` é null quando o mês anterior foi zero: dividir por zero não tem
    resposta, e "aumento de 100%" a partir de nada seria invenção.
    """
    difference = current - previous
    pct = None
    if previous > 0:
        pct = str((difference / previous * 100).quantize(Decimal("0.1")))
    return {
        "current": money(current),
        "previous": money(previous),
        "delta": money(difference),
        "delta_pct": pct,
        "direction": "up" if difference > 0 else "down" if difference < 0 else "flat",
    }


# --------------------------------------------------------------------------
# 1. Mês contra mês
# --------------------------------------------------------------------------


async def month_over_month(current_user: CurrentUser, month_start: date) -> dict:
    """Compara com o mês anterior, **cortando os dois no mesmo dia** quando o mês
    de referência está em curso.

    Sem esse corte, dia 5 de agosto compararia 5 dias contra 31 e o app diria
    "você gastou 80% menos" todo começo de mês — a mentira mais fácil de contar
    com esses dados.
    """
    today = today_local()
    start, end = month_bounds(month_start)
    in_progress = start <= today < end
    cutoff_day = today.day if in_progress else None

    current_rows = await _fetch_range(current_user.household_id, start, end)
    previous_start = previous_month(month_start)
    previous_rows = await _fetch_range(current_user.household_id, *month_bounds(previous_start))

    current = _expenses(_cut(current_rows, cutoff_day))
    previous = _expenses(_cut(previous_rows, cutoff_day))

    current_buckets = _by_bucket(current)
    previous_buckets = _by_bucket(previous)

    return {
        "month": month_start.strftime("%Y-%m"),
        "previous_month": previous_start.strftime("%Y-%m"),
        # A tela precisa dizer "parcial" em vez de anunciar economia que não
        # existe. Cliente que ignora isso mostra número enganoso.
        "partial": in_progress,
        "comparable_days": cutoff_day,
        "total": _delta(_sum(current), _sum(previous)),
        "by_bucket": [
            {
                "bucket": bucket,
                "label": BUCKET_LABELS[bucket],
                **_delta(current_buckets[bucket], previous_buckets[bucket]),
            }
            for bucket in BUCKETS
            if bucket != "poupanca"
        ],
        "by_category": _category_movers(current, previous),
    }


def _cut(rows: list[dict], cutoff_day: int | None) -> list[dict]:
    if cutoff_day is None:
        return rows
    return [row for row in rows if int(row["occurred_at"][8:10]) <= cutoff_day]


def _category_movers(current: list[dict], previous: list[dict]) -> list[dict]:
    """Categorias ordenadas pela variação absoluta — o que mais mudou primeiro.

    Ordena por valor, não por percentual: 200% de aumento em algo de R$ 3 não é
    notícia, e R$ 400 a mais no mercado é.
    """
    names: dict[int | None, str] = {}
    now: dict[int | None, Decimal] = defaultdict(Decimal)
    before: dict[int | None, Decimal] = defaultdict(Decimal)

    for rows, target in ((current, now), (previous, before)):
        for row in rows:
            category = row.get("categories") or {}
            key = category.get("id")
            names.setdefault(key, category.get("name") or "Sem categoria")
            target[key] += to_decimal(row["amount"])

    movers = [
        {"category_id": key, "name": names[key], **_delta(now[key], before[key])}
        for key in set(now) | set(before)
    ]
    movers.sort(key=lambda entry: abs(to_decimal(entry["delta"])), reverse=True)
    return movers


# --------------------------------------------------------------------------
# 2. Assinaturas recorrentes
# --------------------------------------------------------------------------


async def recurring_subscriptions(current_user: CurrentUser) -> dict:
    """Detecta assinatura a partir das transações, **não** da tabela
    `recurring_subscriptions`.

    A tabela existe no schema mas nada escreve nela, e ler dela devolveria lista
    vazia pra sempre — um endpoint que responde 200 e não serve pra nada é pior
    que um que não existe. Detectar sob demanda também não precisa de job.

    Reusa `merchant_key` do import: ela já descarta número e ruído de descritor
    de cartão, que é o que faz "NETFLIX.COM 1234" e "NETFLIX.COM 5678" serem o
    mesmo comerciante.
    """
    today = today_local()
    end = month_bounds(today.replace(day=1))[1]
    start = add_months(today.replace(day=1), -SUBSCRIPTION_WINDOW_MONTHS)

    # Sem aporte, como em todo insight deste módulo. Um investimento mensal de
    # valor fixo passaria em todos os testes de recorrência e entraria somado no
    # `monthly_total`, que a tela apresenta como custo fixo — e aporte não é custo.
    rows = _expenses(await _fetch_range(current_user.household_id, start, end))

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = merchant_key(row.get("merchant") or "")
        if key:
            groups[key].append(row)

    items = []
    for key, entries in groups.items():
        months = {entry["occurred_at"][:7] for entry in entries}
        if len(months) < MIN_MONTHS_FOR_SUBSCRIPTION:
            continue

        amounts = sorted(to_decimal(entry["amount"]) for entry in entries)
        typical = amounts[len(amounts) // 2]
        if not _amounts_are_stable(amounts, typical):
            continue

        newest = max(entries, key=lambda entry: entry["occurred_at"])
        category = newest.get("categories") or {}
        items.append(
            {
                "merchant_key": key,
                "label": (newest.get("merchant") or key).strip(),
                "amount": money(typical),
                "months_seen": len(months),
                "last_seen": newest["occurred_at"],
                "cadence": "monthly",
                "category": (
                    {"id": category.get("id"), "name": category.get("name")} if category else None
                ),
                # Sinaliza o que parou de aparecer, em vez de listar junto sem
                # aviso: assinatura cancelada continuaria "ativa" na tela.
                "active": newest["occurred_at"][:7]
                >= previous_month(today.replace(day=1)).strftime("%Y-%m"),
            }
        )

    items.sort(key=lambda entry: to_decimal(entry["amount"]), reverse=True)
    active = [entry for entry in items if entry["active"]]

    return {
        "months_analyzed": SUBSCRIPTION_WINDOW_MONTHS,
        "items": items,
        # Soma só das ativas: incluir cancelada inflaria o "custo fixo mensal".
        "monthly_total": money(sum((to_decimal(e["amount"]) for e in active), Decimal("0"))),
    }


def _amounts_are_stable(amounts: list[Decimal], typical: Decimal) -> bool:
    """Assinatura tem valor previsível. Sem esta checagem, um supermercado
    visitado todo mês entraria na lista como se fosse mensalidade."""
    if typical <= 0:
        return False
    limit = typical * SUBSCRIPTION_AMOUNT_TOLERANCE
    return all(abs(amount - typical) <= limit for amount in amounts)


# --------------------------------------------------------------------------
# 3. Maiores gastos do mês
# --------------------------------------------------------------------------


async def top_transactions(current_user: CurrentUser, month_start: date, limit: int) -> dict:
    if limit < 1:
        limit = DEFAULT_TOP_LIMIT
    limit = min(limit, MAX_TOP_LIMIT)

    rows = await _fetch_range(current_user.household_id, *month_bounds(month_start))
    expenses = _expenses(rows)
    # Soma o aporte direto do bucket, e não por diferença de listas: comparar
    # dicts com `not in` é O(n²) e quebraria se dois lançamentos fossem iguais.
    savings = _sum(
        [
            row
            for row in rows
            if row.get("type") == "expense"
            and (row.get("categories") or {}).get("bucket") == "poupanca"
        ]
    )

    expenses.sort(key=lambda row: to_decimal(row["amount"]), reverse=True)

    return {
        "month": month_start.strftime("%Y-%m"),
        "items": [
            {
                "id": row["id"],
                "occurred_at": row["occurred_at"],
                "merchant": row.get("merchant"),
                "amount": money(to_decimal(row["amount"])),
                "category": row.get("categories"),
            }
            for row in expenses[:limit]
        ],
        # Diz quanto ficou de fora, em vez de sumir com o aporte em silêncio: um
        # aporte grande seria o "maior gasto" do mês e não é gasto.
        "excluded_savings": money(savings),
    }


# --------------------------------------------------------------------------
# 4. Média de três meses
# --------------------------------------------------------------------------


async def three_month_average(current_user: CurrentUser) -> dict:
    """Média dos meses **fechados**, ignorando mês sem gasto nenhum.

    Mês vazio quase sempre é "não registrei", não "não gastei" — a mesma leitura
    que o `goal_hit` da spec 07 e o baseline da reserva fazem. Incluí-lo como
    zero derrubaria a média e faria o mês corrente parecer um desastre.
    """
    current_start = today_local().replace(day=1)
    month = previous_month(current_start)

    used: list[str] = []
    totals: list[Decimal] = []
    buckets: dict[str, list[Decimal]] = {bucket: [] for bucket in BUCKETS}

    for _ in range(AVERAGE_MONTHS):
        rows = _expenses(await _fetch_range(current_user.household_id, *month_bounds(month)))
        total = _sum(rows)
        if total > 0:
            used.append(month.strftime("%Y-%m"))
            totals.append(total)
            month_buckets = _by_bucket(rows)
            for bucket in BUCKETS:
                buckets[bucket].append(month_buckets[bucket])
        month = previous_month(month)

    if not totals:
        return {
            "months_used": [],
            "average_total": None,
            "by_bucket": [],
            "current_month": None,
        }

    average = (sum(totals) / len(totals)).quantize(Decimal("0.01"))
    current_rows = _expenses(
        await _fetch_range(current_user.household_id, *month_bounds(current_start))
    )
    spent = _sum(current_rows)

    return {
        "months_used": used,
        "average_total": money(average),
        "by_bucket": [
            {
                "bucket": bucket,
                "label": BUCKET_LABELS[bucket],
                "average": money(
                    (sum(buckets[bucket]) / len(buckets[bucket])).quantize(Decimal("0.01"))
                ),
            }
            for bucket in BUCKETS
            if bucket != "poupanca"
        ],
        "current_month": {
            "month": current_start.strftime("%Y-%m"),
            "spent": money(spent),
            # Sem percentual contra a média: o mês corrente está incompleto, e
            # "40% abaixo da média" no dia 10 é sempre verdade e nunca útil. A
            # comparação honesta é a projeção, que já existe na spec 07.
            "partial": True,
        },
    }


# --------------------------------------------------------------------------
# 5. Detalhe do health score
# --------------------------------------------------------------------------


async def health_score_breakdown(current_user: CurrentUser, month_start: date) -> dict:
    """Abre a conta do número que a Home mostra.

    Reusa `compute_health_score`, que já devolve o breakdown por bucket — a nota
    não pode ser calculada de dois jeitos diferentes em dois lugares.
    """
    household_id = current_user.household_id

    rule = await targets_module.get_budget_rule(household_id)
    month_targets = await targets_module.ensure_month_targets(household_id, month_start)
    rows = await targets_module.fetch_month_transactions(household_id, month_start)
    totals = targets_module.aggregate_month(rows)

    result = compute_health_score(rule, totals.by_bucket, month_targets)

    if result is None:
        # Sem renda no mês não existe teto, e sem teto não há aderência a medir.
        # Devolve 200 com a razão, não 404: a tela precisa explicar, não errar.
        return {
            "month": month_start.strftime("%Y-%m"),
            "score": None,
            "label": None,
            "reason": "sem_renda",
            "breakdown": [],
            "uncategorized_expense": money(totals.uncategorized_expense),
        }

    return {
        "month": month_start.strftime("%Y-%m"),
        "score": result["score"],
        "label": result["label"],
        "reason": None,
        "breakdown": [
            {
                **entry,
                "label": BUCKET_LABELS[entry["bucket"]],
                # Teto vs meta muda a leitura: em necessidades/desejos ficar
                # abaixo é bom, em poupança é ficar devendo.
                "kind": "goal" if entry["bucket"] == "poupanca" else "ceiling",
            }
            for entry in result["breakdown"]
        ],
        # Despesa sem categoria não entra em bucket nenhum, então não pontua e
        # não pune. Aparece aqui pra tela poder dizer que a nota ignora esse
        # valor, em vez de o usuário achar que o score já considerou tudo.
        "uncategorized_expense": money(totals.uncategorized_expense),
    }
