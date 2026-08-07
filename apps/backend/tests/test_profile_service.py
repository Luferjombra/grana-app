from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.profile import service
from app.profile.schemas import IncomeCreate, OnboardingPayload
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)


def base_tables(**extra):
    tables = {
        "profiles": [{"id": "user-1", "full_name": "Jo", "income_profile": None}],
        "incomes": [],
        "budget_targets": [],
        "budget_rules": [
            {
                "household_id": 42,
                "necessidades_pct": 50,
                "desejos_pct": 30,
                "poupanca_pct": 20,
            }
        ],
        "household_members": [{"household_id": 42, "user_id": "user-1"}],
        "emergency_reserve": [],
    }
    tables.update(extra)
    return tables


def install(monkeypatch, db, today=date(2026, 8, 15)):
    monkeypatch.setattr(service, "get_db", lambda: db)
    monkeypatch.setattr(targets_module, "get_db", lambda: db)
    monkeypatch.setattr(service, "today_local", lambda: today)
    return db


# --------------------------------------------------------------------------
# Validação
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", ["pj", "", "CLT", "estagiario"])
def test_onboarding_rejects_unknown_profile(profile):
    with pytest.raises(ValidationError):
        OnboardingPayload(income_profile=profile, monthly_income="8000")


@pytest.mark.parametrize("amount", ["0", "-1"])
def test_onboarding_rejects_non_positive_income(amount):
    with pytest.raises(ValidationError):
        OnboardingPayload(income_profile="clt", monthly_income=amount)


# --------------------------------------------------------------------------
# GET /profile
# --------------------------------------------------------------------------


async def test_profile_reports_incomplete_onboarding_without_income(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    profile = await service.get_profile(USER)

    assert profile["onboarding_complete"] is False
    assert profile["current_income"] is None


async def test_profile_reports_complete_with_income(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                incomes=[
                    {
                        "user_id": "user-1",
                        "amount": "8000",
                        "effective_month": "2026-08-01",
                        "source": "salario",
                    }
                ]
            )
        ),
    )

    profile = await service.get_profile(USER)

    assert profile["onboarding_complete"] is True
    assert profile["current_income"] == "8000.00"


async def test_profile_missing_row_is_404(monkeypatch):
    install(monkeypatch, FakeDb(base_tables(profiles=[])))

    with pytest.raises(HTTPException) as exc_info:
        await service.get_profile(USER)
    assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# POST /onboarding
# --------------------------------------------------------------------------


async def test_onboarding_writes_profile_income_and_reserve(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    result = await service.complete_onboarding(
        USER, OnboardingPayload(income_profile="clt", monthly_income="8000")
    )

    assert db.rows("profiles")[0]["income_profile"] == "clt"

    income = db.rows("incomes")[0]
    assert income["amount"] == "8000"
    assert income["effective_month"] == "2026-08-01"
    assert income["source"] == "salario"

    reserve = db.rows("emergency_reserve")[0]
    assert reserve["profile"] == "clt"
    assert reserve["months_multiplier"] == 6
    # 50% da renda, o percentual de necessidades vigente.
    assert reserve["essential_expenses_baseline"] == "4000.00"

    assert result["onboarding_complete"] is True


async def test_failure_before_income_leaves_onboarding_retryable(monkeypatch):
    """A renda é o último passo porque onboarding_complete deriva dela: se algo
    antes falhar, o usuário precisa continuar pendente pra ser trazido de volta
    ao fluxo, em vez de ficar 'concluído' sem reserva pra sempre."""
    db = install(monkeypatch, FakeDb(base_tables()))

    original_execute = db.execute

    def fail_on_reserve(q):
        if q.table == "emergency_reserve":
            raise RuntimeError("indisponível")
        return original_execute(q)

    monkeypatch.setattr(db, "execute", fail_on_reserve)

    with pytest.raises(RuntimeError):
        await service.complete_onboarding(
            USER, OnboardingPayload(income_profile="clt", monthly_income="8000")
        )

    monkeypatch.setattr(db, "execute", original_execute)
    assert db.rows("incomes") == []
    assert (await service.get_profile(USER))["onboarding_complete"] is False


async def test_autonomo_gets_a_longer_reserve(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    await service.complete_onboarding(
        USER, OnboardingPayload(income_profile="autonomo", monthly_income="5000")
    )

    assert db.rows("emergency_reserve")[0]["months_multiplier"] == 12


async def test_reserve_baseline_follows_edited_budget_rule(monkeypatch):
    db = install(
        monkeypatch,
        FakeDb(
            base_tables(
                budget_rules=[
                    {
                        "household_id": 42,
                        "necessidades_pct": 70,
                        "desejos_pct": 20,
                        "poupanca_pct": 10,
                    }
                ]
            )
        ),
    )

    await service.complete_onboarding(
        USER, OnboardingPayload(income_profile="clt", monthly_income="8000")
    )

    assert db.rows("emergency_reserve")[0]["essential_expenses_baseline"] == "5600.00"


# --------------------------------------------------------------------------
# POST /incomes
# --------------------------------------------------------------------------


async def test_income_defaults_to_the_current_month(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    await service.create_income(USER, IncomeCreate(amount="9000"))

    assert db.rows("incomes")[0]["effective_month"] == "2026-08-01"


async def test_income_accepts_an_explicit_month(monkeypatch):
    db = install(monkeypatch, FakeDb(base_tables()))

    await service.create_income(USER, IncomeCreate(amount="9000", effective_month="2026-10"))

    assert db.rows("incomes")[0]["effective_month"] == "2026-10-01"


async def test_income_rejects_invalid_month(monkeypatch):
    install(monkeypatch, FakeDb(base_tables()))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_income(USER, IncomeCreate(amount="9000", effective_month="outubro"))
    assert exc_info.value.status_code == 422


def target_row(month, household_id=42):
    return {
        "household_id": household_id,
        "month": month,
        "bucket": "necessidades",
        "target_amount": "4000",
    }


async def test_declaring_income_clears_targets_from_that_month_onward(monkeypatch):
    """A renda vale do mês declarado em diante (specs/10), então tetos já
    materializados de meses posteriores também estão obsoletos — e
    ensure_month_targets não sobrescreve o que existe."""
    db = install(
        monkeypatch,
        FakeDb(
            base_tables(
                budget_targets=[
                    target_row("2026-07-01"),
                    target_row("2026-08-01"),
                    target_row("2026-09-01"),
                ]
            )
        ),
    )

    await service.create_income(USER, IncomeCreate(amount="10000"))

    # Julho é anterior à declaração: segue valendo o salário antigo.
    assert [row["month"] for row in db.rows("budget_targets")] == ["2026-07-01"]


async def test_clearing_targets_does_not_touch_other_households(monkeypatch):
    db = install(
        monkeypatch,
        FakeDb(base_tables(budget_targets=[target_row("2026-08-01", household_id=99)])),
    )

    await service.create_income(USER, IncomeCreate(amount="10000"))

    assert len(db.rows("budget_targets")) == 1


async def test_list_incomes_only_returns_own(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            base_tables(
                incomes=[
                    {
                        "id": 1,
                        "user_id": "user-1",
                        "amount": "8000",
                        "effective_month": "2026-08-01",
                        "source": "salario",
                    },
                    {
                        "id": 2,
                        "user_id": "outro",
                        "amount": "1",
                        "effective_month": "2026-08-01",
                        "source": "salario",
                    },
                ]
            )
        ),
    )

    incomes = await service.list_incomes(USER)

    assert [row["id"] for row in incomes] == [1]
    assert incomes[0]["amount"] == "8000.00"
