import pytest
from fastapi import HTTPException

from app.auth import CurrentUser
from app.budget import service
from app.budget import targets as targets_module
from app.budget.schemas import BudgetRuleUpdate
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)

CATEGORIES = {
    1: {"id": 1, "name": "Moradia", "bucket": "necessidades", "icon": "ti-home"},
    2: {"id": 2, "name": "Lazer", "bucket": "desejos", "icon": "ti-ticket"},
    3: {"id": 3, "name": "Investimentos", "bucket": "poupanca", "icon": "ti-trending-up"},
}


def tx(amount, category_id, type="expense", occurred_at="2026-08-05", household_id=42):
    """A embed `categories(...)` do PostgREST vem como chave aninhada no row."""
    return {
        "amount": amount,
        "type": type,
        "occurred_at": occurred_at,
        "category_id": category_id,
        "household_id": household_id,
        "categories": CATEGORIES.get(category_id),
    }


def install_db(monkeypatch, db: FakeDb):
    monkeypatch.setattr(service, "get_db", lambda: db)
    monkeypatch.setattr(targets_module, "get_db", lambda: db)
    return db


def base_tables(transactions=None, **extra):
    tables = {
        "transactions": transactions or [],
        "budget_rules": [
            {
                "household_id": 42,
                "necessidades_pct": 50,
                "desejos_pct": 30,
                "poupanca_pct": 20,
            }
        ],
        "budget_targets": [],
        "household_members": [{"household_id": 42, "user_id": "user-1"}],
        "incomes": [],
    }
    tables.update(extra)
    return tables


async def test_summary_splits_income_and_expense(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(
            base_tables(
                [
                    tx("8000", None, type="income"),
                    tx("1800", 1),
                    tx("500", 2),
                ]
            )
        ),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")

    assert summary["cash_flow"]["income"] == "8000.00"
    assert summary["cash_flow"]["expense"] == "2300.00"
    assert summary["cash_flow"]["net"] == "5700.00"


async def test_summary_ignores_other_households(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(base_tables([tx("1800", 1), tx("9999", 1, household_id=99)])),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")

    assert summary["cash_flow"]["expense"] == "1800.00"


async def test_summary_groups_by_category_with_percentages(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(base_tables([tx("750", 1), tx("250", 2)])),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")
    by_category = {item["name"]: item for item in summary["by_category"]}

    assert by_category["Moradia"]["amount"] == "750.00"
    assert by_category["Moradia"]["percentage"] == "75.0"
    assert by_category["Lazer"]["percentage"] == "25.0"


async def test_summary_category_list_is_sorted_by_amount(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(base_tables([tx("100", 1), tx("900", 2)])),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")

    assert [item["name"] for item in summary["by_category"]] == ["Lazer", "Moradia"]


async def test_summary_with_no_transactions_does_not_divide_by_zero(monkeypatch):
    install_db(monkeypatch, FakeDb(base_tables([])))

    summary = await service.get_dashboard_summary(USER, "2026-08")

    assert summary["cash_flow"]["expense"] == "0.00"
    assert summary["by_category"] == []


async def test_summary_without_income_has_no_targets_and_no_score(monkeypatch):
    """Sem renda cadastrada não dá pra derivar teto — mostra gasto, sem meta."""
    install_db(monkeypatch, FakeDb(base_tables([tx("1800", 1)])))

    summary = await service.get_dashboard_summary(USER, "2026-08")

    assert summary["health_score"] is None
    assert all(bucket["target"] is None for bucket in summary["buckets"])
    assert summary["buckets"][0]["spent"] == "1800.00"


async def test_summary_generates_and_persists_targets_from_income(monkeypatch):
    db = install_db(
        monkeypatch,
        FakeDb(
            base_tables(
                [tx("1800", 1)],
                incomes=[{"user_id": "user-1", "amount": "8000", "effective_month": "2026-08-01"}],
            )
        ),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")
    buckets = {b["bucket"]: b for b in summary["buckets"]}

    assert buckets["necessidades"]["target"] == "4000.00"
    assert buckets["desejos"]["target"] == "2400.00"
    assert buckets["poupanca"]["target"] == "1600.00"
    # Persistiu, pra permitir override manual depois (specs/07).
    assert len(db.rows("budget_targets")) == 3


async def test_summary_respects_manually_overridden_target(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(
            base_tables(
                [tx("1800", 1)],
                incomes=[{"user_id": "user-1", "amount": "8000", "effective_month": "2026-08-01"}],
                budget_targets=[
                    {
                        "household_id": 42,
                        "month": "2026-08-01",
                        "bucket": "necessidades",
                        "target_amount": "3000",
                    }
                ],
            )
        ),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")
    buckets = {b["bucket"]: b for b in summary["buckets"]}

    assert buckets["necessidades"]["target"] == "3000.00"


async def test_summary_sums_income_across_household_members(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(
            base_tables(
                [],
                household_members=[
                    {"household_id": 42, "user_id": "user-1"},
                    {"household_id": 42, "user_id": "user-2"},
                ],
                incomes=[
                    {"user_id": "user-1", "amount": "5000", "effective_month": "2026-08-01"},
                    {"user_id": "user-2", "amount": "3000", "effective_month": "2026-08-01"},
                    {"user_id": "user-3", "amount": "9999", "effective_month": "2026-08-01"},
                ],
            )
        ),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")
    buckets = {b["bucket"]: b for b in summary["buckets"]}

    # 8000 de renda somada dos dois membros; user-3 não é do household.
    assert buckets["necessidades"]["target"] == "4000.00"


async def test_summary_ignores_income_from_another_month(monkeypatch):
    install_db(
        monkeypatch,
        FakeDb(
            base_tables(
                [],
                incomes=[{"user_id": "user-1", "amount": "8000", "effective_month": "2026-07-01"}],
            )
        ),
    )

    summary = await service.get_dashboard_summary(USER, "2026-08")

    assert summary["health_score"] is None


async def test_summary_rejects_invalid_month(monkeypatch):
    install_db(monkeypatch, FakeDb(base_tables([])))

    with pytest.raises(HTTPException) as exc_info:
        await service.get_dashboard_summary(USER, "agosto")
    assert exc_info.value.status_code == 422


async def test_get_budget_rule_falls_back_to_default(monkeypatch):
    install_db(monkeypatch, FakeDb(base_tables([], budget_rules=[])))

    rule = await service.get_budget_rule(USER)

    assert rule["necessidades_pct"] == "50"
    assert rule["desejos_pct"] == "30"
    assert rule["poupanca_pct"] == "20"


async def test_update_budget_rule_persists(monkeypatch):
    db = install_db(monkeypatch, FakeDb(base_tables([])))

    await service.update_budget_rule(
        USER, BudgetRuleUpdate(necessidades_pct="60", desejos_pct="20", poupanca_pct="20")
    )

    saved = db.queries[-2].payload
    assert saved["necessidades_pct"] == "60"
    assert saved["household_id"] == 42
