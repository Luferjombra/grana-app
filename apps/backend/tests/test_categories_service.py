from app.auth import CurrentUser
from app.categories import service
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)


def category(id, name, bucket, household_id=None, is_default=True):
    return {
        "id": id,
        "name": name,
        "bucket": bucket,
        "icon": "ti-x",
        "is_default": is_default,
        "household_id": household_id,
    }


def install(monkeypatch, rows):
    db = FakeDb({"categories": rows})
    monkeypatch.setattr(service, "get_db", lambda: db)
    return db


async def test_scopes_to_defaults_plus_own_household(monkeypatch):
    """O backend usa service role (ignora RLS), então o escopo tem que ser
    aplicado na query — o `or_` é montado com o household do token."""
    db = install(monkeypatch, [])

    await service.list_categories(USER)

    clause = db.queries[-1].or_clauses[0]
    assert "household_id.is.null" in clause
    assert "household_id.eq.42" in clause


async def test_orders_by_bucket_then_name(monkeypatch):
    install(
        monkeypatch,
        [
            category(1, "Investimentos", "poupanca"),
            category(2, "Lazer", "desejos"),
            category(3, "Moradia", "necessidades"),
            category(4, "Contas", "necessidades"),
        ],
    )

    result = await service.list_categories(USER)

    # Ordem 50-30-20, e alfabética dentro de cada bucket.
    assert [row["name"] for row in result] == ["Contas", "Moradia", "Lazer", "Investimentos"]


async def test_does_not_leak_household_id(monkeypatch):
    install(monkeypatch, [category(1, "Moradia", "necessidades", household_id=42)])

    result = await service.list_categories(USER)

    assert "household_id" not in result[0]
    assert result[0]["name"] == "Moradia"


async def test_unknown_bucket_goes_last_instead_of_crashing(monkeypatch):
    install(
        monkeypatch,
        [category(1, "Estranha", "outro"), category(2, "Moradia", "necessidades")],
    )

    result = await service.list_categories(USER)

    assert [row["name"] for row in result] == ["Moradia", "Estranha"]
