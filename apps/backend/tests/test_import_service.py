import io
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.auth import CurrentUser
from app.imports import rules, service
from app.imports.parser import MAX_ROWS
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
    tables = {"transactions": [], "categories": list(SEED_CATEGORIES), "import_rules": []}
    tables.update(extra)
    return tables


def install(monkeypatch, db):
    # `rules` tem o próprio `get_db` importado, então patchar só o do `service`
    # deixaria as regras batendo no Supabase real.
    monkeypatch.setattr(service, "get_db", lambda: db)
    monkeypatch.setattr(rules, "get_db", lambda: db)
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

    assert result == {
        "imported": 0,
        "skipped": 1,
        "months_touched": [],
        # A regra é aprendida mesmo sem nada pra importar: o usuário gastou a
        # escolha, e descartá-la porque o extrato já tinha entrado faria o
        # próximo arquivo cobrar o mesmo trabalho.
        "rules_learned": 1,
    }
    assert len(db.rows("transactions")) == 1
    assert len(db.rows("import_rules")) == 1


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


# --------------------------------------------------------------------------
# Um mês por vez + regras aprendidas (specs/11)
# --------------------------------------------------------------------------

# Três meses no mesmo arquivo, o padrão de um extrato de histórico.
OFX_MULTI = """<OFX>
<STMTTRN><DTPOSTED>20241205<TRNAMT>-90.00<FITID>D1<MEMO>MERCEARIA VILA NOVA</STMTTRN>
<STMTTRN><DTPOSTED>20241220<TRNAMT>-60.00<FITID>D2<MEMO>MERCEARIA VILA NOVA SP</STMTTRN>
<STMTTRN><DTPOSTED>20241110<TRNAMT>-45.00<FITID>N1<MEMO>MERCEARIA VILA NOVA 123</STMTTRN>
<STMTTRN><DTPOSTED>20241015<TRNAMT>-30.00<FITID>O1<MEMO>BARBEARIA NORTE</STMTTRN>
</OFX>"""


async def test_preview_defaults_to_the_most_recent_month(monkeypatch):
    """Extrato de 12 meses cobraria 169 decisões de uma vez; o fluxo é um mês por
    vez, e o mais recente primeiro porque é o mais barato e faz o painel do mês
    corrente viver na hora (specs/11)."""
    install(monkeypatch, FakeDb(base_tables()))

    preview = await service.preview_import(USER, upload(OFX_MULTI.encode(), "extrato.ofx"))

    assert preview["month"] == "2024-12"
    assert [entry["month"] for entry in preview["months"]] == ["2024-12", "2024-11", "2024-10"]
    assert [entry["total"] for entry in preview["months"]] == [2, 1, 1]
    # só dezembro entra no preview, não o arquivo todo
    assert preview["summary"]["total"] == 2


async def test_preview_accepts_an_explicit_month(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    preview = await service.preview_import(
        USER, upload(OFX_MULTI.encode(), "extrato.ofx"), month="2024-10"
    )

    assert preview["month"] == "2024-10"
    assert preview["summary"]["total"] == 1
    assert all_items(preview)[0]["description"] == "BARBEARIA NORTE"


async def test_preview_rejects_month_absent_from_the_file(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    with pytest.raises(HTTPException) as exc:
        await service.preview_import(
            USER, upload(OFX_MULTI.encode(), "extrato.ofx"), month="2023-01"
        )

    assert exc.value.status_code == 422


async def test_preview_applies_the_learned_rule(monkeypatch):
    """O ponto do funil: a escolha de um mês resolve os outros. "MERCEARIA VILA
    NOVA" não casa com nenhuma palavra-chave, mas a regra aprendida preenche."""
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                import_rules=[
                    {
                        "id": 1,
                        "household_id": 42,
                        "merchant_key": "MERCEARIA VILA NOVA",
                        "category_id": 2,
                    }
                ]
            )
        ),
    )

    preview = await service.preview_import(
        USER, upload(OFX_MULTI.encode(), "extrato.ofx"), month="2024-11"
    )

    assert all_items(preview)[0]["category_id"] == 2
    assert preview["summary"]["suggested"] == 1


async def test_learned_rule_beats_the_keyword_guess(monkeypatch):
    """`suggest.RULES` é só o palpite de quem nunca importou nada. Se o usuário já
    corrigiu esse comerciante, reofertar o genérico desfaria o aprendizado."""
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                # "Mercado" casaria com a palavra-chave -> categoria 1
                import_rules=[
                    {"id": 1, "household_id": 42, "merchant_key": "MERCADO", "category_id": 3}
                ]
            )
        ),
    )

    preview = await service.preview_import(USER, upload(CSV.encode(), "extrato.csv"))

    despesa = next(item for item in all_items(preview) if item["type"] == "expense")
    assert despesa["category_id"] == 3


async def test_preview_ignores_rule_from_another_household(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                import_rules=[
                    {
                        "id": 1,
                        "household_id": OTHER_HOUSEHOLD,
                        "merchant_key": "MERCEARIA VILA NOVA",
                        "category_id": 2,
                    }
                ]
            )
        ),
    )

    preview = await service.preview_import(
        USER, upload(OFX_MULTI.encode(), "extrato.ofx"), month="2024-11"
    )

    assert all_items(preview)[0]["category_id"] is None


async def test_confirm_learns_one_rule_per_merchant(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(
        USER,
        ImportConfirm(
            rows=[
                row(description="MERCEARIA VILA NOVA", category_id=1, external_id="ofx:A"),
                row(description="MERCEARIA VILA NOVA SP 123", category_id=1, external_id="ofx:B"),
                row(description="BARBEARIA NORTE", category_id=2, external_id="ofx:C"),
            ]
        ),
    )

    assert result["rules_learned"] == 2
    learned = {r["merchant_key"]: r["category_id"] for r in db.rows("import_rules")}
    assert learned == {"MERCEARIA VILA NOVA": 1, "BARBEARIA NORTE": 2}
    assert all(r["household_id"] == 42 for r in db.rows("import_rules"))


async def test_confirm_does_not_learn_from_an_ambiguous_merchant(monkeypatch):
    """O caso "BOLETO" do extrato real: a descrição é só "BOLETO" + número, e o
    número é descartado, então cobranças de natureza diferente caem na mesma
    chave. Se o usuário tirou um item do grupo e deu outra categoria, gravar a
    última criaria uma regra que erra em silêncio nos próximos meses. Melhor não
    sugerir do que sugerir errado (specs/11).

    Nota: "BOLETO ENERGIA" e "BOLETO ESCOLA" *não* colidem — merchant_key usa 3
    palavras. A colisão real vem de descrição sem palavra útil além do "BOLETO".
    """
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(
        USER,
        ImportConfirm(
            rows=[
                row(description="BOLETO 0001234", category_id=1, external_id="ofx:A"),
                row(description="BOLETO 99887766", category_id=2, external_id="ofx:B"),
            ]
        ),
    )

    assert result["rules_learned"] == 0
    assert db.rows("import_rules") == []


async def test_confirm_overwrites_the_rule_of_the_same_merchant(monkeypatch):
    """Reescolher a categoria corrige a regra, em vez de acumular duas
    contraditórias — depende do unique (household_id, merchant_key)."""
    db = install(
        monkeypatch,
        FakeDb(
            base_tables(
                import_rules=[
                    {
                        "id": 1,
                        "household_id": 42,
                        "merchant_key": "BARBEARIA NORTE",
                        "category_id": 1,
                    }
                ]
            )
        ),
    )

    await service.confirm_import(
        USER,
        ImportConfirm(
            rows=[row(description="BARBEARIA NORTE", category_id=3, external_id="ofx:Z")]
        ),
    )

    assert len(db.rows("import_rules")) == 1
    assert db.rows("import_rules")[0]["category_id"] == 3


async def test_confirm_does_not_learn_from_income(monkeypatch):
    """Regra é só (comerciante -> categoria), sem tipo. Aprender de receita faria
    um PIX recebido da mesma pessoa cair numa categoria de gasto."""
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(
        USER,
        ImportConfirm(
            rows=[
                row(
                    type="income", description="PIX ANA BEATRIZ", category_id=1, external_id="ofx:A"
                )
            ]
        ),
    )

    assert result["rules_learned"] == 0
    assert db.rows("import_rules") == []


async def test_preview_does_not_group_transactions_without_description(monkeypatch):
    """No extrato real, 49 despesas não tinham descrição alguma e somavam
    R$ 115.177 — de R$ 0,02 a R$ 23.395. Todas caíam numa chave vazia, e uma
    escolha só jogaria esse valor inteiro numa categoria (specs/11)."""
    install(monkeypatch, FakeDb(base_tables()))
    content = (
        "Data;Descrição;Valor\n"
        "05/08/2026;;-0,02\n"
        "06/08/2026;;-23395,00\n"
        "07/08/2026;   ;-19,16\n"
    ).encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["summary"]["merchants"] == 3
    assert all(group["count"] == 1 for group in result["groups"])
    assert all(group["merchant_key"] == "" for group in result["groups"])


async def test_preview_does_not_group_description_made_only_of_noise(monkeypatch):
    """Chave vazia não é só descrição vazia: "Osasco OSASCO BRA" é só cidade e
    país, tudo em NOISE_TOKENS, e sobra nada pra agrupar por."""
    install(monkeypatch, FakeDb(base_tables()))
    content = (
        "Data;Descrição;Valor\n"
        "05/08/2026;Osasco       OSASCO      BRA;-10,00\n"
        "06/08/2026;26/03/2024;-20,00\n"
    ).encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["summary"]["merchants"] == 2


async def test_confirm_does_not_learn_a_rule_without_merchant_key(monkeypatch):
    """Regra com chave vazia casaria com todo lançamento sem descrição — o oposto
    do que o desagrupamento acima protege."""
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.confirm_import(
        USER, ImportConfirm(rows=[row(description="", category_id=1, external_id="ofx:A")])
    )

    assert result["rules_learned"] == 0
    assert db.rows("import_rules") == []


async def test_income_only_group_does_not_need_a_category(monkeypatch):
    """Só despesa exige categoria (specs/09). Sem esta flag a tela cobraria
    decisão de grupo de entrada — no extrato real, 3 dos 28 grupos de dezembro."""
    install(monkeypatch, FakeDb(base_tables()))
    content = "Data;Descrição;Valor\n05/08/2026;SALARIO ACME;8.000,00\n".encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["groups"][0]["needs_category"] is False


async def test_group_with_any_expense_needs_a_category(monkeypatch):
    """Grupo misto existe no extrato real (compra e venda do mesmo ativo caem na
    mesma chave): basta uma despesa pra exigir categoria."""
    install(monkeypatch, FakeDb(base_tables()))
    content = (
        "Data;Descrição;Valor\n"
        "05/08/2026;CORRETORA ACOES FLCR;-500,00\n"
        "06/08/2026;CORRETORA ACOES FLCR;300,00\n"
    ).encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["groups"][0]["count"] == 2
    assert result["groups"][0]["needs_category"] is True


async def test_preview_refuses_a_file_at_the_row_cap(monkeypatch):
    """Recusa em vez de truncar. O parser para em MAX_ROWS lendo do começo, e
    extrato é cronológico crescente, então o corte descarta os lançamentos mais
    NOVOS — o mês default sairia de um mês do meio apresentado como o mais
    recente, e o usuário importaria um mês antigo achando que era o atual."""
    install(monkeypatch, FakeDb(base_tables()))
    linhas = "".join(f"05/08/2026;LOJA {n};-10,00\n" for n in range(MAX_ROWS + 5))
    content = ("Data;Descrição;Valor\n" + linhas).encode()

    with pytest.raises(HTTPException) as exc:
        await service.preview_import(USER, upload(content, "extrato.csv"))

    assert exc.value.status_code == 422
    assert "período menor" in exc.value.detail


async def test_preview_accepts_a_file_just_under_the_cap(monkeypatch):
    """O extrato real validado tem 1.059 lançamentos: o teto não pode atrapalhar
    o caso normal de 12 meses."""
    install(monkeypatch, FakeDb(base_tables()))
    linhas = "".join(f"05/08/2026;LOJA {n};-10,00\n" for n in range(MAX_ROWS - 1))
    content = ("Data;Descrição;Valor\n" + linhas).encode()

    result = await service.preview_import(USER, upload(content, "extrato.csv"))

    assert result["summary"]["total"] == MAX_ROWS - 1
