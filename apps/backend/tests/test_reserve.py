from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.reserve import service
from app.reserve.schemas import ReserveUpdate
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)
TODAY = date(2026, 8, 15)


def reserve(**over):
    row = {
        "household_id": 42,
        "profile": "clt",
        "essential_expenses_baseline": "4000.00",
        "months_multiplier": 6,
        "current_balance": "0.00",
    }
    row.update(over)
    return row


def install(monkeypatch, db, essential: dict[str, str] | None = None):
    """`essential` mapeia 'AAAA-MM' -> gasto em necessidades daquele mês."""
    monkeypatch.setattr(service, "get_db", lambda: db)
    monkeypatch.setattr(service, "today_local", lambda: TODAY)

    async def fake_fetch(household_id, month_start):
        return [{"month": month_start.strftime("%Y-%m")}]

    def fake_aggregate(rows):
        key = list(rows)[0]["month"]
        amount = Decimal((essential or {}).get(key, "0"))
        return targets_module.MonthTotals(
            income=Decimal("0"),
            expense=amount,
            by_bucket={"necessidades": amount},
            by_category={},
            uncategorized_expense=Decimal("0"),
        )

    monkeypatch.setattr(targets_module, "fetch_month_transactions", fake_fetch)
    monkeypatch.setattr(targets_module, "aggregate_month", fake_aggregate)
    return db


# --------------------------------------------------------------------------
# GET
# --------------------------------------------------------------------------


async def test_get_computes_target_from_baseline_and_multiplier(monkeypatch):
    install(monkeypatch, FakeDb({"emergency_reserve": [reserve()]}))

    result = await service.get_reserve(USER)

    assert result["target"] == "24000.00"  # 4000 × 6
    assert result["missing"] == "24000.00"
    assert result["progress_pct"] == 0
    assert result["complete"] is False


async def test_get_reports_progress_and_months_covered(monkeypatch):
    install(monkeypatch, FakeDb({"emergency_reserve": [reserve(current_balance="14000.00")]}))

    result = await service.get_reserve(USER)

    assert result["progress_pct"] == 58
    assert result["missing"] == "10000.00"
    # "3,5 meses de vida" diz mais ao usuário que "58%"
    assert result["months_covered"] == "3.5"


async def test_progress_stops_at_100_when_over_target(monkeypatch):
    install(monkeypatch, FakeDb({"emergency_reserve": [reserve(current_balance="30000.00")]}))

    result = await service.get_reserve(USER)

    assert result["progress_pct"] == 100
    assert result["missing"] == "0.00"
    assert result["complete"] is True


async def test_get_without_reserve_sends_the_user_back_to_onboarding(monkeypatch):
    install(monkeypatch, FakeDb({"emergency_reserve": []}))

    with pytest.raises(HTTPException) as exc:
        await service.get_reserve(USER)

    assert exc.value.status_code == 404
    assert "onboarding" in exc.value.detail


# --------------------------------------------------------------------------
# Sugestão de baseline
# --------------------------------------------------------------------------


async def test_suggests_baseline_from_real_essential_spending(monkeypatch):
    """O baseline nasce estimado no onboarding (renda × % necessidades). Com
    histórico, a sugestão vem do gasto que de fato aconteceu."""
    install(
        monkeypatch,
        FakeDb({"emergency_reserve": [reserve()]}),
        essential={"2026-07": "6000.00", "2026-06": "6000.00", "2026-05": "6000.00"},
    )

    result = await service.get_reserve(USER)

    assert result["suggested_baseline"] == {
        "amount": "6000.00",
        "months_used": 3,
        "direction": "up",
    }
    # sugerir não é sobrescrever: o valor guardado continua o mesmo
    assert result["essential_expenses_baseline"] == "4000.00"


async def test_does_not_suggest_when_the_difference_is_noise(monkeypatch):
    install(
        monkeypatch,
        FakeDb({"emergency_reserve": [reserve()]}),
        essential={"2026-07": "4050.00", "2026-06": "4050.00", "2026-05": "4050.00"},
    )

    result = await service.get_reserve(USER)

    # ~1% de diferença: sugerir isso ensinaria o usuário a ignorar o aviso
    assert result["suggested_baseline"] is None


async def test_ignores_months_without_spending_in_the_average(monkeypatch):
    """Mês sem gasto quase sempre é "não registrei", não "não gastei" — mesma
    leitura que o goal_hit da spec 07 faz."""
    install(
        monkeypatch,
        FakeDb({"emergency_reserve": [reserve()]}),
        essential={"2026-07": "9000.00", "2026-06": "0", "2026-05": "0"},
    )

    result = await service.get_reserve(USER)

    # média de [9000], não de [9000, 0, 0] = 3000
    assert result["suggested_baseline"]["amount"] == "9000.00"


async def test_does_not_suggest_without_any_history(monkeypatch):
    install(monkeypatch, FakeDb({"emergency_reserve": [reserve()]}))

    result = await service.get_reserve(USER)

    assert result["suggested_baseline"] is None


async def test_suggestion_ignores_the_current_month(monkeypatch):
    """Agosto está incompleto e puxaria a média pra baixo."""
    install(
        monkeypatch,
        FakeDb({"emergency_reserve": [reserve()]}),
        essential={"2026-08": "100.00", "2026-07": "8000.00"},
    )

    result = await service.get_reserve(USER)

    assert result["suggested_baseline"]["amount"] == "8000.00"


# --------------------------------------------------------------------------
# PATCH
# --------------------------------------------------------------------------


async def test_patch_profile_moves_the_multiplier_along(monkeypatch):
    """Perfil e multiplicador andam juntos: "autônomo com 6 meses" não é escolha
    que a tela oferece e seria estado inconsistente."""
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()]}))

    result = await service.update_reserve(USER, ReserveUpdate(profile="autonomo"))

    assert result["months_multiplier"] == 12
    assert result["target"] == "48000.00"
    assert db.rows("emergency_reserve")[0]["months_multiplier"] == 12


async def test_patch_records_the_balance_the_user_informed(monkeypatch):
    """Nada mais escreve current_balance. Sem isto a reserva teria meta e nenhuma
    forma de dizer quanto já existe, e o alerta reserve_progress da spec 07
    ficaria dormente pra sempre."""
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()]}))

    result = await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("5000")))

    assert result["current_balance"] == "5000.00"
    assert db.rows("emergency_reserve")[0]["current_balance"] == "5000"


async def test_patch_baseline_alone_keeps_the_profile(monkeypatch):
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()]}))

    result = await service.update_reserve(
        USER, ReserveUpdate(essential_expenses_baseline=Decimal("3000"))
    )

    assert result["profile"] == "clt"
    assert result["target"] == "18000.00"
    assert db.rows("emergency_reserve")[0]["months_multiplier"] == 6


async def test_patch_only_touches_the_household_of_the_caller(monkeypatch):
    db = install(
        monkeypatch,
        FakeDb({"emergency_reserve": [reserve(), reserve(household_id=99, profile="autonomo")]}),
    )

    await service.update_reserve(USER, ReserveUpdate(profile="autonomo"))

    other = next(row for row in db.rows("emergency_reserve") if row["household_id"] == 99)
    assert other["months_multiplier"] == 6  # não foi tocado


async def test_patch_without_reserve_is_404(monkeypatch):
    install(monkeypatch, FakeDb({"emergency_reserve": []}))

    with pytest.raises(HTTPException) as exc:
        await service.update_reserve(USER, ReserveUpdate(profile="clt"))

    assert exc.value.status_code == 404


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


def test_patch_rejects_an_empty_body():
    with pytest.raises(ValidationError):
        ReserveUpdate()


def test_patch_rejects_unknown_profile():
    with pytest.raises(ValidationError):
        ReserveUpdate(profile="pj")


def test_patch_rejects_negative_balance():
    with pytest.raises(ValidationError):
        ReserveUpdate(current_balance=Decimal("-1"))


def test_patch_rejects_zero_baseline():
    with pytest.raises(ValidationError):
        ReserveUpdate(essential_expenses_baseline=Decimal("0"))


def test_balance_stays_decimal():
    """Valor monetário nunca vira float no caminho (specs/09)."""
    assert ReserveUpdate(current_balance=Decimal("1234.56")).current_balance == Decimal("1234.56")


# --------------------------------------------------------------------------
# Marco da reserva (destrava o reserve_progress que a spec 07 adiou)
# --------------------------------------------------------------------------


def install_engine(monkeypatch, db):
    from app.notifications import engine

    monkeypatch.setattr(engine, "get_db", lambda: db)
    monkeypatch.setattr(engine, "today_local", lambda: TODAY)

    async def members(household_id):
        return ["user-1"]

    monkeypatch.setattr(engine, "_household_member_ids", members)
    return db


async def test_patch_creates_the_reserve_milestone(monkeypatch):
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()], "notifications": []}))
    install_engine(monkeypatch, db)

    # 12.000 com baseline de 4.000 = 3 meses cobertos
    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("12000")))

    alerts = db.rows("notifications")
    assert [a["subject"] for a in alerts] == ["3"]
    assert alerts[0]["type"] == "reserve_progress"
    assert alerts[0]["severity"] == "info"


async def test_milestone_reports_only_the_highest_reached(monkeypatch):
    """Passar de 1 pra 6 meses de uma vez não pode gerar quatro alertas."""
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()], "notifications": []}))
    install_engine(monkeypatch, db)

    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("24000")))

    subjects = sorted(a["subject"] for a in db.rows("notifications"))
    # 6 meses cobertos E meta batida (4000 × 6)
    assert subjects == ["6", "complete"]


async def test_milestone_is_created_once_in_a_lifetime(monkeypatch):
    """`_upsert_unread` chaveia por mês, o que é certo pra alerta de teto. Marco
    não: atingir 3 meses acontece uma vez, e a chave mensal faria o app
    reparabenizar todo dia 1."""
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()], "notifications": []}))
    install_engine(monkeypatch, db)

    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("12000")))
    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("13000")))

    assert len(db.rows("notifications")) == 1


async def test_milestone_survives_the_user_lowering_the_balance(monkeypatch):
    """Marco é conquista, então não é reconciliado — igual ao goal_hit."""
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()], "notifications": []}))
    install_engine(monkeypatch, db)

    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("12000")))
    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("100")))

    assert len(db.rows("notifications")) == 1


async def test_no_milestone_below_one_month(monkeypatch):
    db = install(monkeypatch, FakeDb({"emergency_reserve": [reserve()], "notifications": []}))
    install_engine(monkeypatch, db)

    await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("500")))

    assert db.rows("notifications") == []


async def test_patch_still_succeeds_when_the_alert_fails(monkeypatch):
    """O saldo já foi gravado: devolver erro num pedido que deu certo seria pior
    que perder o alerta."""
    install(monkeypatch, FakeDb({"emergency_reserve": [reserve()], "notifications": []}))

    async def explode(*_args, **_kwargs):
        raise RuntimeError("migration 0003 não aplicada")

    monkeypatch.setattr(service, "evaluate_reserve", explode)

    result = await service.update_reserve(USER, ReserveUpdate(current_balance=Decimal("12000")))

    assert result["current_balance"] == "12000.00"


async def test_zero_baseline_is_not_a_complete_reserve(monkeypatch):
    """Com baseline zerado o alvo é zero, e `balance >= target` diria "reserva
    completa" pra quem não tem nada guardado."""
    install(monkeypatch, FakeDb({"emergency_reserve": [reserve(essential_expenses_baseline="0")]}))

    result = await service.get_reserve(USER)

    assert result["complete"] is False
    assert result["progress_pct"] == 0
    assert result["months_covered"] is None
