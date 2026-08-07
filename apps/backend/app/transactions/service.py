import asyncio
from datetime import date

from fastapi import HTTPException

from app.auth import CurrentUser
from app.common import add_months, money, month_bounds, parse_month, split_installments, to_decimal
from app.db import get_db
from app.transactions.schemas import TransactionCreate, TransactionUpdate

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100

# Colunas explícitas em vez de "*": raw_payload guarda a resposta bruta do
# provedor (Mindee/Pluggy) e pode ter dezenas de KB por linha — o app não usa,
# e numa página de 30 itens isso domina o payload.
TRANSACTION_COLUMNS = (
    "id, household_id, user_id, account_id, category_id, type, amount, occurred_at, "
    "merchant, note, entry_method, receipt_id, external_transaction_id, "
    "installment_number, installment_total, created_at, "
    "categories(id, name, bucket, icon)"
)


def _serialize(row: dict) -> dict:
    return {**row, "amount": money(to_decimal(row["amount"]))}


def _encode_cursor(row: dict) -> str:
    return f"{row['occurred_at']}:{row['id']}"


def _decode_cursor(cursor: str) -> tuple[str, int]:
    """Valida a data como data de verdade antes de interpolar no filtro do
    PostgREST — sem isso, dava pra fechar o grupo `or(...)` pelo cursor e
    injetar condições arbitrárias na consulta."""
    try:
        raw_date, raw_id = cursor.rsplit(":", 1)
        occurred_at = date.fromisoformat(raw_date)
        return occurred_at.isoformat(), int(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cursor inválido.") from exc


async def list_transactions(
    current_user: CurrentUser,
    month: str | None = None,
    category_id: int | None = None,
    type: str | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict:
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    query = (
        get_db()
        .table("transactions")
        .select(TRANSACTION_COLUMNS)
        .eq("household_id", current_user.household_id)
    )

    if month:
        start, end = month_bounds(parse_month(month))
        query = query.gte("occurred_at", start.isoformat()).lt("occurred_at", end.isoformat())
    if category_id is not None:
        query = query.eq("category_id", category_id)
    if type is not None:
        query = query.eq("type", type)

    if cursor:
        # Keyset pagination em (occurred_at, id): offset puro pularia ou
        # repetiria linhas se algo fosse inserido entre duas páginas.
        cursor_date, cursor_id = _decode_cursor(cursor)
        query = query.or_(
            f"occurred_at.lt.{cursor_date}," f"and(occurred_at.eq.{cursor_date},id.lt.{cursor_id})"
        )

    # Busca uma linha a mais que o limite pra saber se existe próxima página
    # sem precisar de um count separado.
    query = query.order("occurred_at", desc=True).order("id", desc=True).limit(limit + 1)
    result = await asyncio.to_thread(query.execute)
    rows = result.data or []

    has_more = len(rows) > limit
    page = rows[:limit]

    return {
        "items": [_serialize(row) for row in page],
        "next_cursor": _encode_cursor(page[-1]) if has_more and page else None,
    }


async def get_transaction(current_user: CurrentUser, transaction_id: int) -> dict:
    query = (
        get_db()
        .table("transactions")
        .select(TRANSACTION_COLUMNS)
        .eq("id", transaction_id)
        .eq("household_id", current_user.household_id)
        .maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    return _serialize(result.data)


async def _assert_category_visible(current_user: CurrentUser, category_id: int) -> None:
    """Categoria precisa ser padrão do sistema (household_id null) ou do próprio
    household — sem isso dava pra referenciar categoria de outro household."""
    query = (
        get_db().table("categories").select("id, household_id").eq("id", category_id).maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        raise HTTPException(status_code=422, detail="Categoria não encontrada.")

    household_id = result.data["household_id"]
    if household_id is not None and household_id != current_user.household_id:
        raise HTTPException(status_code=422, detail="Categoria não encontrada.")


async def create_transaction(current_user: CurrentUser, data: TransactionCreate) -> dict:
    if data.category_id is not None:
        await _assert_category_visible(current_user, data.category_id)

    try:
        first_date = date.fromisoformat(data.occurred_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Data inválida. Use YYYY-MM-DD.") from exc

    rows = _build_installment_rows(current_user, data, first_date)

    query = get_db().table("transactions").insert(rows)
    result = await asyncio.to_thread(query.execute)

    created = result.data or []
    # Devolve a parcela do mês corrente; quem chama só precisa do id e da data
    # pra reavaliar os alertas. `installments_created` evita que o cliente
    # tenha que deduzir se houve expansão.
    return {**_serialize(created[0]), "installments_created": len(created)}


def _build_installment_rows(
    current_user: CurrentUser, data: TransactionCreate, first_date: date
) -> list[dict]:
    """Compra parcelada vira uma transação por parcela, uma em cada mês.

    Sem isso, marcar 12x lançaria o valor cheio no mês atual e deixaria os 11
    meses seguintes parecendo livres do compromisso — justamente o que um app
    de orçamento não pode errar (specs/09, decisão de produto do CLAUDE.md).
    """
    total_installments = data.installment_total or 1
    amounts = split_installments(data.amount, total_installments)

    base = {
        "user_id": current_user.user_id,
        "household_id": current_user.household_id,
        "category_id": data.category_id,
        "type": data.type,
        "merchant": data.merchant,
        "note": data.note,
        "entry_method": "manual",
    }

    if total_installments == 1:
        return [
            {
                **base,
                "amount": str(amounts[0]),
                "occurred_at": first_date.isoformat(),
                "installment_number": None,
                "installment_total": None,
            }
        ]

    return [
        {
            **base,
            "amount": str(amount),
            "occurred_at": add_months(first_date, index).isoformat(),
            "installment_number": index + 1,
            "installment_total": total_installments,
        }
        for index, amount in enumerate(amounts)
    ]


async def update_transaction(
    current_user: CurrentUser, transaction_id: int, data: TransactionUpdate
) -> dict:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    if changes.get("category_id") is not None:
        await _assert_category_visible(current_user, changes["category_id"])
    if "amount" in changes and changes["amount"] is not None:
        changes["amount"] = str(changes["amount"])

    query = (
        get_db()
        .table("transactions")
        .update(changes)
        .eq("id", transaction_id)
        .eq("household_id", current_user.household_id)
    )
    result = await asyncio.to_thread(query.execute)
    if not result.data:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    return _serialize(result.data[0])


async def delete_transaction(current_user: CurrentUser, transaction_id: int) -> dict:
    """Devolve a linha removida — quem chama precisa do occurred_at pra saber
    qual mês reavaliar no motor de alertas."""
    query = (
        get_db()
        .table("transactions")
        .delete()
        .eq("id", transaction_id)
        .eq("household_id", current_user.household_id)
    )
    result = await asyncio.to_thread(query.execute)
    if not result.data:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    return _serialize(result.data[0])
