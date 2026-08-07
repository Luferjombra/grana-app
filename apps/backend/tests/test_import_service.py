import io
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.auth import CurrentUser
from app.imports import service
from app.imports.schemas import ImportConfirm, ImportRow
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)
OTHER_HOUSEHOLD = 99

CSV = "Data;Descrição;Valor\n05/08/2026;Mercado;-150,00\n06/08/2026;Salário;8.000,00\n"

OFX = """<OFX><STMTTRN>
<DTPOSTED>20260805<TRNAMT>-150.00<FITID>ABC1<MEMO>MERCADO
</STMTTRN></OFX>"""


def upload(content: bytes, filename: str) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": "text/plain"}),
    )


SEED_CATEGORIES = [
    {"id": 1, "name": "Mercado", "household_id": None},
    {"id": 2, "name": "Transporte", "household_id": None},
    {"id": 3, "name": "Delivery", "household_id": None},
]


def base_tables(**extra):
    tables = {"transactions": [], "categories": list(SEED_CATEGORIES)}
    tables.update(extra)
    return tables


def install(monkeypatch, db):
    monkeypatch.setattr(service, "get_db", lambda: db)
    return db


def all_items(preview: dict) -> list[dict]:
    return [item for group in preview["groups"] for item in group["items"]]


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------


async def test_preview_does_not_persist_anything(monkeypatch):
    """O usuário revisa antes: o preview não pode gravar (specs/11)."""
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.preview_import(USER, upload(CSV.encode(), "extrato.csv"))

    assert len(all_items(result)) == 2
    assert db.rows("transactions") == []


async def test_preview_suggests_category_by_description(monkeypatch):
    """Palavra-chave cobre pouco sozinha (16% num extrato real), mas o que ela
    acerta o usuário não precisa tocar."""
    install(monkeypatch, FakeDb(base_tables()))
    content = "Data;Descrição;Valor\n05/08/2026;SUPERMERCADO XYZ;-150,00\n".encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["groups"][0]["suggested_category_id"] == 1  # Mercado
    assert result["summary"]["suggested"] == 1


async def test_preview_leaves_category_empty_when_nothing_matches(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))
    content = "Data;Descrição;Valor\n05/08/2026;PIX ENVIADO JOAO;-50,00\n".encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    # PIX é meio de pagamento, não categoria — melhor vazio que palpite errado.
    assert result["groups"][0]["suggested_category_id"] is None


async def test_preview_reads_ofx_by_extension(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    result = await service.preview_import(USER, upload(OFX.encode(), "extrato.ofx"))

    assert all_items(result)[0]["external_id"] == "ofx:ABC1"


async def test_preview_groups_the_same_merchant(monkeypatch):
    """O que torna o import de histórico viável: uma escolha vale pelo grupo."""
    install(monkeypatch, FakeDb(base_tables()))
    content = (
        "Data;Descrição;Valor\n"
        "05/08/2026;PADARIA DONA BETINHA SAO PAULO BRA;-12,00\n"
        "06/08/2026;PADARIA DONA BETINHA OSASCO BRA 123;-15,00\n"
        "07/08/2026;POSTO IPIRANGA;-200,00\n"
    ).encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["summary"]["total"] == 3
    # Cidade, "BRA" e número são ruído de descritor de cartão: as duas compras
    # da padaria têm que cair no mesmo grupo.
    assert result["summary"]["merchants"] == 2

    biggest = result["groups"][0]
    assert biggest["count"] == 2
    assert biggest["total"] == "27.00"


async def test_preview_orders_groups_by_volume(monkeypatch):
    """Maior primeiro: o usuário resolve o que mais pesa antes de cansar."""
    install(monkeypatch, FakeDb(base_tables()))
    content = (
        "Data;Descrição;Valor\n"
        "05/08/2026;LOJA UNICA;-10,00\n"
        "06/08/2026;POSTO IPIRANGA;-100,00\n"
        "07/08/2026;POSTO IPIRANGA;-100,00\n"
    ).encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["groups"][0]["count"] == 2


async def test_preview_flags_reimported_ofx_transaction(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                transactions=[
                    {
                        "id": 1,
                        "household_id": 42,
                        "external_transaction_id": "ofx:ABC1",
                        "occurred_at": "2026-08-05",
                        "amount": "150.00",
                        "merchant": "MERCADO",
                    }
                ]
            )
        ),
    )

    result = await service.preview_import(USER, upload(OFX.encode(), "extrato.ofx"))

    assert all_items(result)[0]["likely_duplicate"] is True
    assert result["summary"]["likely_duplicates"] == 1


async def test_preview_flags_csv_duplicate_by_signature(monkeypatch):
    """CSV não tem id do banco, então compara data+valor+descrição."""
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                transactions=[
                    {
                        "id": 1,
                        "household_id": 42,
                        "external_transaction_id": None,
                        "occurred_at": "2026-08-05",
                        "amount": "150.00",
                        "merchant": "Mercado",
                    }
                ]
            )
        ),
    )

    result = await service.preview_import(USER, upload(CSV.encode(), "extrato.csv"))
    by_date = {item["occurred_at"]: item for item in all_items(result)}

    assert by_date["2026-08-05"]["likely_duplicate"] is True
    assert by_date["2026-08-06"]["likely_duplicate"] is False


async def test_preview_ignores_transaction_from_another_household(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                transactions=[
                    {
                        "id": 1,
                        "household_id": OTHER_HOUSEHOLD,
                        "external_transaction_id": "ofx:ABC1",
                        "occurred_at": "2026-08-05",
                        "amount": "150.00",
                        "merchant": "MERCADO",
                    }
                ]
            )
        ),
    )

    result = await service.preview_import(USER, upload(OFX.encode(), "extrato.ofx"))

    assert all_items(result)[0]["likely_duplicate"] is False


async def test_preview_rejects_empty_file(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    with pytest.raises(HTTPException) as exc_info:
        await service.preview_import(USER, upload(b"", "extrato.csv"))
    assert exc_info.value.status_code == 400


async def test_preview_rejects_oversized_file(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))
    monkeypatch.setattr(service, "MAX_UPLOAD_BYTES", 10)

    with pytest.raises(HTTPException) as exc_info:
        await service.preview_import(USER, upload(CSV.encode(), "extrato.csv"))
    assert exc_info.value.status_code == 400


async def test_preview_explains_when_it_cannot_read_the_file(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    with pytest.raises(HTTPException) as exc_info:
        await service.preview_import(USER, upload(b"nada a ver\n", "extrato.csv"))
    assert exc_info.value.status_code == 422


# --------------------------------------------------------------------------
# Confirmação
# --------------------------------------------------------------------------


def row(**overrides):
    payload = {
        "amount": "150.00",
        "type": "expense",
        "occurred_at": "2026-08-05",
        "description": "Mercado",
        "category_id": 1,
    }
    payload.update(overrides)
    return ImportRow(**payload)


async def test_confirm_creates_transactions_marked_as_import(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(USER, ImportConfirm(rows=[row()]))

    created = db.rows("transactions")[0]
    assert created["entry_method"] == "csv_import"
    assert created["household_id"] == 42
    assert created["merchant"] == "Mercado"
    assert result["imported"] == 1


async def test_confirm_reports_months_touched(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(
        USER,
        ImportConfirm(
            rows=[
                row(occurred_at="2026-07-30"),
                row(occurred_at="2026-08-05"),
                row(occurred_at="2026-08-20"),
            ]
        ),
    )

    # Quem chama usa isso pra reavaliar os alertas de cada mês afetado.
    assert result["months_touched"] == ["2026-07", "2026-08"]


async def test_confirm_skips_what_was_already_imported(monkeypatch):
    """Reimportar o mesmo extrato não pode duplicar nem falhar o lote."""
    db = install(
        monkeypatch,
        FakeDb(
            base_tables(
                transactions=[
                    {
                        "id": 1,
                        "household_id": 42,
                        "external_transaction_id": "ofx:ABC1",
                        "occurred_at": "2026-08-05",
                        "amount": "150.00",
                        "merchant": "MERCADO",
                    }
                ]
            )
        ),
    )

    result = await service.confirm_import(
        USER,
        ImportConfirm(
            rows=[
                row(external_id="ofx:ABC1"),
                row(external_id="ofx:NOVO", occurred_at="2026-08-06"),
            ]
        ),
    )

    assert result["imported"] == 1
    assert result["skipped"] == 1
    assert len(db.rows("transactions")) == 2


async def test_confirm_dedupes_repeated_id_inside_the_same_file(monkeypatch):
    """Extrato com período sobreposto repete FITID; sem isso as duas linhas
    batem no índice único e derrubam o insert em lote."""
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(
        USER,
        ImportConfirm(rows=[row(external_id="ofx:ABC1"), row(external_id="ofx:ABC1")]),
    )

    assert result["imported"] == 1
    assert result["skipped"] == 1
    assert len(db.rows("transactions")) == 1


async def test_confirm_keeps_identical_csv_rows(monkeypatch):
    """Dois cafés iguais no mesmo dia são legítimos: sem id do banco, não dedupe."""
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(USER, ImportConfirm(rows=[row(), row()]))

    assert result["imported"] == 2
    assert result["skipped"] == 0
    assert len(db.rows("transactions")) == 2


async def test_confirm_with_everything_already_imported_does_nothing(monkeypatch):
    db = install(
        monkeypatch,
        FakeDb(
            base_tables(
                transactions=[
                    {
                        "id": 1,
                        "household_id": 42,
                        "external_transaction_id": "ofx:ABC1",
                        "occurred_at": "2026-08-05",
                        "amount": "150.00",
                        "merchant": "MERCADO",
                    }
                ]
            )
        ),
    )

    result = await service.confirm_import(USER, ImportConfirm(rows=[row(external_id="ofx:ABC1")]))

    assert result == {"imported": 0, "skipped": 1, "months_touched": []}
    assert len(db.rows("transactions")) == 1


async def test_confirm_ignores_id_already_used_by_another_household(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                transactions=[
                    {
                        "id": 1,
                        "household_id": OTHER_HOUSEHOLD,
                        "external_transaction_id": "ofx:ABC1",
                        "occurred_at": "2026-08-05",
                        "amount": "150.00",
                        "merchant": "MERCADO",
                    }
                ]
            )
        ),
    )

    result = await service.confirm_import(USER, ImportConfirm(rows=[row(external_id="ofx:ABC1")]))

    assert result["imported"] == 1


async def test_confirm_rejects_category_from_another_household(monkeypatch):
    install(
        monkeypatch,
        FakeDb(base_tables(categories=[{"id": 7, "household_id": OTHER_HOUSEHOLD}])),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_import(USER, ImportConfirm(rows=[row(category_id=7)]))
    assert exc_info.value.status_code == 422


async def test_confirm_rejects_unknown_category(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_import(USER, ImportConfirm(rows=[row(category_id=404)]))
    assert exc_info.value.status_code == 422


async def test_confirm_rejects_malformed_date(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_import(USER, ImportConfirm(rows=[row(occurred_at="05/08/2026")]))
    assert exc_info.value.status_code == 422


async def test_income_does_not_need_a_category(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    await service.confirm_import(USER, ImportConfirm(rows=[row(type="income", category_id=None)]))

    assert db.rows("transactions")[0]["type"] == "income"


def test_expense_without_category_is_rejected_by_the_schema():
    """Mesma regra do lançamento manual: sem categoria o gasto escaparia
    da regra 50-30-20."""
    with pytest.raises(ValidationError):
        row(type="expense", category_id=None)


def test_schema_rejects_non_positive_amount():
    with pytest.raises(ValidationError):
        row(amount="0")


def test_schema_rejects_transfer_from_statement():
    with pytest.raises(ValidationError):
        row(type="transfer")


def test_schema_rejects_empty_confirmation():
    with pytest.raises(ValidationError):
        ImportConfirm(rows=[])


def test_schema_keeps_amount_as_decimal():
    """Valor monetário nunca vira float no caminho (specs/09)."""
    assert row(amount="1234.56").amount == Decimal("1234.56")
