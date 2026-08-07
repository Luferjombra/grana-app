import asyncio
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, UploadFile

from app.auth import CurrentUser
from app.common import money, to_decimal
from app.db import get_db
from app.imports.parser import MAX_ROWS, ParsedRow, parse_csv, parse_ofx
from app.imports.schemas import ImportConfirm, ImportRow
from app.imports.suggest import merchant_key, normalize, suggest_category_id

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def preview_import(current_user: CurrentUser, file: UploadFile) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo maior que o limite de 5MB.")

    filename = (file.filename or "").lower()
    try:
        rows = parse_ofx(content) if filename.endswith(".ofx") else parse_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(
            status_code=422, detail="Não encontrei lançamentos que eu saiba ler nesse arquivo."
        )

    already_imported = await _existing_external_ids(current_user, rows)
    existing_signatures = await _existing_signatures(current_user, rows)
    categories_by_name = await _categories_by_name(current_user)

    items = []
    for row in rows:
        # OFX: id do banco já existe -> reimportação, bloqueada pelo índice.
        # CSV: sem id, então compara data+valor+descrição e só avisa.
        duplicate = (
            row.external_id in already_imported
            if row.external_id
            else _signature(row) in existing_signatures
        )
        items.append(
            {
                "occurred_at": row.occurred_at.isoformat(),
                "amount": money(row.amount),
                "type": row.type,
                "description": row.description,
                "external_id": row.external_id,
                "likely_duplicate": duplicate,
                "category_id": suggest_category_id(row.description, categories_by_name),
            }
        )

    groups = _group_by_merchant(rows, items)

    return {
        "groups": groups,
        "summary": {
            "total": len(items),
            "merchants": len(groups),
            "suggested": sum(1 for item in items if item["category_id"] is not None),
            "likely_duplicates": sum(1 for item in items if item["likely_duplicate"]),
            # Avisa quando o arquivo foi cortado, em vez de deixar o usuário
            # achar que importou tudo.
            "truncated": len(rows) >= MAX_ROWS,
        },
    }


def _group_by_merchant(rows: list[ParsedRow], items: list[dict]) -> list[dict]:
    """Agrupa por comerciante pra uma escolha valer pelo grupo inteiro.

    É o que torna o import de histórico viável: num extrato real de um ano,
    951 despesas vinham de 169 comerciantes, e ~44 escolhas cobriam 80% delas.
    Item a item seriam 951 decisões e o usuário abandonaria (specs/11).

    Ordenado por quantidade: o usuário resolve primeiro o que mais pesa.
    """
    buckets: dict[str, dict] = {}

    for row, item in zip(rows, items, strict=True):
        key = merchant_key(row.description) or "(sem descrição)"
        bucket = buckets.setdefault(
            key,
            {
                "merchant_key": key,
                "label": row.description.strip() or "Sem descrição",
                "suggested_category_id": item["category_id"],
                "items": [],
            },
        )
        # A sugestão do grupo é a primeira que aparecer: linhas do mesmo
        # comerciante caem na mesma regra, então não há conflito real.
        if bucket["suggested_category_id"] is None:
            bucket["suggested_category_id"] = item["category_id"]
        bucket["items"].append(item)

    groups = []
    for bucket in buckets.values():
        expenses = [item for item in bucket["items"] if item["type"] == "expense"]
        groups.append(
            {
                **bucket,
                "count": len(bucket["items"]),
                "total": money(
                    sum((to_decimal(item["amount"]) for item in expenses), Decimal("0"))
                ),
                "likely_duplicates": sum(1 for item in bucket["items"] if item["likely_duplicate"]),
            }
        )

    return sorted(groups, key=lambda group: group["count"], reverse=True)


async def _categories_by_name(current_user: CurrentUser) -> dict[str, int]:
    query = (
        get_db()
        .table("categories")
        .select("id, name, household_id")
        .or_(f"household_id.is.null,household_id.eq.{current_user.household_id}")
    )
    result = await asyncio.to_thread(query.execute)
    return {normalize(row["name"]): row["id"] for row in (result.data or [])}


def _signature(row: ParsedRow) -> tuple[str, str, str]:
    return (row.occurred_at.isoformat(), money(row.amount), row.description.strip().lower())


async def _existing_external_ids(current_user: CurrentUser, rows: list[ParsedRow]) -> set[str]:
    return await _existing_external_ids_from(current_user, [row.external_id for row in rows])


async def _existing_external_ids_from(
    current_user: CurrentUser, candidates: list[str | None]
) -> set[str]:
    ids = [value for value in candidates if value]
    if not ids:
        return set()

    query = (
        get_db()
        .table("transactions")
        .select("external_transaction_id")
        .eq("household_id", current_user.household_id)
        .in_("external_transaction_id", ids)
    )
    result = await asyncio.to_thread(query.execute)
    return {row["external_transaction_id"] for row in (result.data or [])}


async def _existing_signatures(
    current_user: CurrentUser, rows: list[ParsedRow]
) -> set[tuple[str, str, str]]:
    """Compara só dentro do intervalo de datas do arquivo — puxar o histórico
    inteiro do household pra achar duplicata de um mês não se paga."""
    dates = [row.occurred_at for row in rows]
    if not dates:
        return set()

    query = (
        get_db()
        .table("transactions")
        .select("occurred_at, amount, merchant")
        .eq("household_id", current_user.household_id)
        .gte("occurred_at", min(dates).isoformat())
        .lte("occurred_at", max(dates).isoformat())
    )
    result = await asyncio.to_thread(query.execute)

    return {
        (
            row["occurred_at"],
            money(to_decimal(row["amount"])),
            (row.get("merchant") or "").strip().lower(),
        )
        for row in (result.data or [])
    }


async def confirm_import(current_user: CurrentUser, data: ImportConfirm) -> dict:
    category_ids = {row.category_id for row in data.rows if row.category_id is not None}
    await _assert_categories_visible(current_user, category_ids)

    rows, skipped = await _drop_already_imported(current_user, data.rows)
    if not rows:
        return {"imported": 0, "skipped": skipped, "months_touched": []}

    payload = [
        {
            "user_id": current_user.user_id,
            "household_id": current_user.household_id,
            "category_id": row.category_id,
            "type": row.type,
            "amount": str(row.amount),
            "occurred_at": _validated_date(row.occurred_at),
            "merchant": (row.description or "").strip() or None,
            "entry_method": "csv_import",
            "external_transaction_id": row.external_id,
        }
        for row in rows
    ]

    # Insert simples, não upsert com on_conflict: o índice de dedupe é parcial
    # (só onde external_transaction_id não é nulo), e o Postgres não infere
    # índice parcial a partir de lista de colunas — ON CONFLICT (cols) falharia
    # a requisição inteira. Filtrar antes também dá contagem exata de skipped e
    # deixa qualquer outra violação de constraint aparecer, em vez de sumir num
    # DO NOTHING sem alvo.
    query = get_db().table("transactions").insert(payload)
    result = await asyncio.to_thread(query.execute)
    created = result.data or []

    return {
        "imported": len(created),
        "skipped": skipped,
        "months_touched": sorted({row["occurred_at"][:7] for row in payload}),
    }


async def _drop_already_imported(
    current_user: CurrentUser, rows: list[ImportRow]
) -> tuple[list[ImportRow], int]:
    """Remove o que já está no banco e o que se repete dentro do próprio
    arquivo — extrato com período sobreposto tem FITID repetido, e duas linhas
    iguais no mesmo lote batem no índice único e derrubariam o insert todo.

    Vale só pra linha com id do banco: duas despesas iguais de CSV no mesmo dia
    são legítimas (specs/11).
    """
    already = await _existing_external_ids_from(current_user, [row.external_id for row in rows])

    kept: list[ImportRow] = []
    seen: set[str] = set()
    skipped = 0

    for row in rows:
        external_id = row.external_id
        if external_id and (external_id in already or external_id in seen):
            skipped += 1
            continue
        if external_id:
            seen.add(external_id)
        kept.append(row)

    return kept, skipped


def _validated_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Data inválida. Use AAAA-MM-DD.") from exc


async def _assert_categories_visible(current_user: CurrentUser, category_ids: set[int]) -> None:
    if not category_ids:
        return

    query = get_db().table("categories").select("id, household_id").in_("id", list(category_ids))
    result = await asyncio.to_thread(query.execute)

    visible = {
        row["id"]
        for row in (result.data or [])
        if row["household_id"] is None or row["household_id"] == current_user.household_id
    }
    missing = category_ids - visible
    if missing:
        raise HTTPException(status_code=422, detail="Categoria não encontrada.")
