import pytest
from fastapi import HTTPException

from app.auth import CurrentUser
from app.transactions import service
from app.transactions.schemas import TransactionCreate, TransactionUpdate
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)
OTHER_HOUSEHOLD = 99


def transaction_row(**overrides):
    row = {
        "id": 1,
        "household_id": 42,
        "user_id": "user-1",
        "amount": "10.00",
        "type": "expense",
        "occurred_at": "2026-08-05",
        "category_id": 1,
    }
    row.update(overrides)
    return row


def install_db(monkeypatch, db: FakeDb):
    monkeypatch.setattr(service, "get_db", lambda: db)
    return db


async def test_list_only_returns_own_household(monkeypatch):
    db = install_db(
        monkeypatch,
        FakeDb(
            {
                "transactions": [
                    transaction_row(id=1),
                    transaction_row(id=2, household_id=OTHER_HOUSEHOLD),
                ]
            }
        ),
    )

    result = await service.list_transactions(USER)

    assert [item["id"] for item in result["items"]] == [1]
    assert db.queries[0].filters["household_id"] == 42


async def test_list_filters_by_month_using_half_open_range(monkeypatch):
    db = install_db(monkeypatch, FakeDb({"transactions": []}))

    await service.list_transactions(USER, month="2026-12")

    filters = db.queries[-1].filters
    assert filters["occurred_at__gte"] == "2026-12-01"
    # Dezembro precisa fechar em 2027-01-01, não 2026-13-01.
    assert filters["occurred_at__lt"] == "2027-01-01"


async def test_list_returns_cursor_only_when_more_pages_exist(monkeypatch):
    rows = [transaction_row(id=i, occurred_at="2026-08-05") for i in range(1, 6)]
    install_db(monkeypatch, FakeDb({"transactions": rows}))

    page = await service.list_transactions(USER, limit=2)

    assert len(page["items"]) == 2
    assert page["next_cursor"] is not None


async def test_list_last_page_has_no_cursor(monkeypatch):
    install_db(monkeypatch, FakeDb({"transactions": [transaction_row(id=1)]}))

    page = await service.list_transactions(USER, limit=10)

    assert page["next_cursor"] is None


async def test_list_caps_page_size(monkeypatch):
    db = install_db(monkeypatch, FakeDb({"transactions": []}))

    await service.list_transactions(USER, limit=10_000)

    assert db.queries[-1].limit_value == service.MAX_PAGE_SIZE + 1


async def test_list_applies_keyset_cursor_clause(monkeypatch):
    db = install_db(monkeypatch, FakeDb({"transactions": []}))

    await service.list_transactions(USER, cursor="2026-08-05:7")

    clause = db.queries[-1].or_clauses[0]
    assert "occurred_at.lt.2026-08-05" in clause
    assert "and(occurred_at.eq.2026-08-05,id.lt.7)" in clause


@pytest.mark.parametrize(
    "cursor",
    [
        "lixo",
        "2026-08-05",
        "2026-08-05:abc",
        "nao-e-data:7",
        "2026-13-45:7",
        # Tentativa de fechar o grupo or(...) e injetar filtro extra.
        "2026-08-05),id.gt.0,and(id.gt.0:1",
    ],
)
async def test_list_rejects_malformed_or_injected_cursor(monkeypatch, cursor):
    install_db(monkeypatch, FakeDb({"transactions": []}))

    with pytest.raises(HTTPException) as exc_info:
        await service.list_transactions(USER, cursor=cursor)
    assert exc_info.value.status_code == 422


async def test_list_does_not_expose_raw_provider_payload(monkeypatch):
    db = install_db(monkeypatch, FakeDb({"transactions": []}))

    await service.list_transactions(USER)

    assert "raw_payload" not in service.TRANSACTION_COLUMNS
    assert db.queries[-1].table == "transactions"


async def test_get_transaction_from_other_household_is_404(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb({"transactions": [transaction_row(id=1, household_id=OTHER_HOUSEHOLD)]}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_transaction(USER, 1)
    assert exc_info.value.status_code == 404


async def test_create_stamps_household_and_entry_method(monkeypatch):
    db = install_db(
        monkeypatch,
        FakeDb({"transactions": [], "categories": [{"id": 1, "household_id": None}]}),
    )

    created = await service.create_transaction(
        USER,
        TransactionCreate(amount="25.50", type="expense", occurred_at="2026-08-05", category_id=1),
    )

    assert created["household_id"] == 42
    assert created["user_id"] == "user-1"
    assert created["entry_method"] == "manual"
    assert created["amount"] == "25.50"
    assert db.rows("transactions")


async def test_create_accepts_default_system_category(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb({"transactions": [], "categories": [{"id": 1, "household_id": None}]}),
    )

    created = await service.create_transaction(
        USER,
        TransactionCreate(amount="10", type="expense", occurred_at="2026-08-05", category_id=1),
    )
    assert created["category_id"] == 1


async def test_create_rejects_category_from_another_household(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(
            {
                "transactions": [],
                "categories": [{"id": 7, "household_id": OTHER_HOUSEHOLD}],
            }
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_transaction(
            USER,
            TransactionCreate(amount="10", type="expense", occurred_at="2026-08-05", category_id=7),
        )
    assert exc_info.value.status_code == 422


async def test_create_rejects_unknown_category(monkeypatch):
    install_db(monkeypatch, FakeDb({"transactions": [], "categories": []}))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_transaction(
            USER,
            TransactionCreate(
                amount="10", type="expense", occurred_at="2026-08-05", category_id=404
            ),
        )
    assert exc_info.value.status_code == 422


async def test_update_only_touches_sent_fields(monkeypatch):
    db = install_db(monkeypatch, FakeDb({"transactions": [transaction_row(id=1)]}))

    await service.update_transaction(USER, 1, TransactionUpdate(merchant="Novo"))

    payload = db.queries[-1].payload
    assert payload == {"merchant": "Novo"}


async def test_update_rejects_empty_payload(monkeypatch):
    install_db(monkeypatch, FakeDb({"transactions": [transaction_row(id=1)]}))

    with pytest.raises(HTTPException) as exc_info:
        await service.update_transaction(USER, 1, TransactionUpdate())
    assert exc_info.value.status_code == 422


async def test_update_from_other_household_is_404(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb({"transactions": [transaction_row(id=1, household_id=OTHER_HOUSEHOLD)]}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_transaction(USER, 1, TransactionUpdate(merchant="Novo"))
    assert exc_info.value.status_code == 404


async def test_delete_removes_own_transaction(monkeypatch):
    db = install_db(monkeypatch, FakeDb({"transactions": [transaction_row(id=1)]}))

    await service.delete_transaction(USER, 1)

    assert db.rows("transactions") == []


async def test_delete_from_other_household_is_404(monkeypatch):
    db = install_db(
        monkeypatch,
        FakeDb({"transactions": [transaction_row(id=1, household_id=OTHER_HOUSEHOLD)]}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_transaction(USER, 1)
    assert exc_info.value.status_code == 404
    assert len(db.rows("transactions")) == 1
