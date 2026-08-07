from datetime import date
from decimal import Decimal

import pytest

from app.budget import targets as targets_module
from app.notifications import engine
from tests.fakes import FakeDb

HOUSEHOLD = 42
AUGUST = date(2026, 8, 1)

CATEGORIES = {
    1: {"id": 1, "name": "Moradia", "bucket": "necessidades", "icon": "ti-home"},
    2: {"id": 2, "name": "Lazer", "bucket": "desejos", "icon": "ti-ticket"},
    3: {"id": 3, "name": "Investimentos", "bucket": "poupanca", "icon": "ti-trending-up"},
}


def tx(amount, category_id, type="expense", occurred_at="2026-08-05"):
    return {
        "amount": amount,
        "type": type,
        "occurred_at": occurred_at,
        "category_id": category_id,
        "household_id": HOUSEHOLD,
        "categories": CATEGORIES.get(category_id),
    }


def target(bucket, amount, month="2026-08-01"):
    return {
        "household_id": HOUSEHOLD,
        "month": month,
        "bucket": bucket,
        "target_amount": amount,
    }


ALL_TARGETS = [
    target("necessidades", "4000"),
    target("desejos", "2400"),
    target("poupanca", "1600"),
]


def build_db(transactions=None, targets=None, income="8000", notifications=None, **extra):
    tables = {
        "transactions": transactions or [],
        "budget_targets": targets if targets is not None else [],
        "budget_rules": [
            {
                "household_id": HOUSEHOLD,
                "necessidades_pct": 50,
                "desejos_pct": 30,
                "poupanca_pct": 20,
            }
        ],
        "household_members": [{"household_id": HOUSEHOLD, "user_id": "user-1"}],
        "incomes": (
            [{"user_id": "user-1", "amount": income, "effective_month": "2026-08-01"}]
            if income
            else []
        ),
        "notifications": notifications or [],
    }
    tables.update(extra)
    return FakeDb(tables)


def install(monkeypatch, db):
    monkeypatch.setattr(engine, "get_db", lambda: db)
    monkeypatch.setattr(targets_module, "get_db", lambda: db)
    return db


# --------------------------------------------------------------------------
# compute_projection — função pura
# --------------------------------------------------------------------------


def test_projection_is_none_before_the_minimum_days():
    """Aluguel no dia 1 projetaria ~30x ele mesmo — cedo demais pra confiar."""
    assert engine.compute_projection(Decimal("1800"), AUGUST, date(2026, 8, 1)) is None
    assert engine.compute_projection(Decimal("1800"), AUGUST, date(2026, 8, 6)) is None


def test_projection_starts_at_the_minimum_day():
    result = engine.compute_projection(Decimal("1400"), AUGUST, date(2026, 8, 7))

    assert result is not None
    projection, days = result
    assert days == 7
    # 1400/7 = 200/dia * 31 dias de agosto
    assert projection == Decimal("6200")


def test_projection_of_a_closed_month_uses_every_day():
    result = engine.compute_projection(Decimal("6200"), AUGUST, date(2026, 9, 15))

    projection, days = result
    assert days == 31
    assert projection == Decimal("6200")


def test_projection_of_a_future_month_is_none():
    assert engine.compute_projection(Decimal("0"), AUGUST, date(2026, 7, 20)) is None


# --------------------------------------------------------------------------
# Alerta de teto
# --------------------------------------------------------------------------


async def test_ceiling_alert_fires_at_95_percent(monkeypatch):
    db = install(
        monkeypatch,
        build_db(
            transactions=[tx("3800", 1)],  # 95% de 4000
            targets=[target("necessidades", "4000"), target("desejos", "2400")],
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    types = [n.type for n in pending]
    assert "budget_ceiling" in types
    assert db.rows("notifications")[0]["subject"] == "necessidades"


async def test_ceiling_alert_does_not_fire_below_threshold(monkeypatch):
    install(
        monkeypatch,
        build_db(
            transactions=[tx("3700", 1)],  # 92,5%
            targets=[target("necessidades", "4000")],
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    assert [n for n in pending if n.type == "budget_ceiling"] == []


async def test_savings_bucket_never_triggers_a_ceiling_alert(monkeypatch):
    """Poupança é meta a atingir — guardar muito não é 'estourar'."""
    install(
        monkeypatch,
        build_db(
            transactions=[tx("5000", 3)],
            targets=[target("poupanca", "1600")],
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    assert [n for n in pending if n.type == "budget_ceiling"] == []


async def test_each_bucket_gets_its_own_ceiling_alert(monkeypatch):
    db = install(
        monkeypatch,
        build_db(
            transactions=[tx("3900", 1), tx("2350", 2)],
            targets=[target("necessidades", "4000"), target("desejos", "2400")],
        ),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    subjects = {row["subject"] for row in db.rows("notifications")}
    assert subjects == {"necessidades", "desejos"}


# --------------------------------------------------------------------------
# Alerta de projeção
# --------------------------------------------------------------------------


async def test_projection_alert_fires_above_97_percent_of_income(monkeypatch):
    install(
        monkeypatch,
        build_db(
            # 2000 em 10 dias -> 200/dia -> 6200 no mês, 77,5% de 8000: seguro.
            # 2600 em 10 dias -> 260/dia -> 8060 no mês, acima de 97% de 8000.
            transactions=[tx("2600", 1)],
            targets=[target("necessidades", "4000")],
            income="8000",
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 10))

    assert any(n.type == "negative_projection" for n in pending)


async def test_projection_alert_stays_quiet_when_on_track(monkeypatch):
    install(
        monkeypatch,
        build_db(
            transactions=[tx("2000", 1)],
            targets=[target("necessidades", "4000")],
            income="8000",
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 10))

    assert not any(n.type == "negative_projection" for n in pending)


async def test_no_projection_alert_in_the_first_days(monkeypatch):
    """Mesmo com gasto alto: no dia 3 a projeção ainda não é confiável."""
    install(
        monkeypatch,
        build_db(
            transactions=[tx("3000", 1)],
            targets=[target("necessidades", "4000")],
            income="8000",
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 3))

    assert not any(n.type == "negative_projection" for n in pending)


async def test_following_the_rule_perfectly_does_not_trigger_risk(monkeypatch):
    """Com 50-30-20 a saída planejada é 100% da renda. Se o aporte contasse
    como gasto, quem cumpre a meta levaria alerta de risco todo mês."""
    install(
        monkeypatch,
        build_db(
            transactions=[
                tx("1290", 1),  # necessidades, no ritmo de 4000/mês
                tx("774", 2),  # desejos, no ritmo de 2400/mês
                tx("516", 3),  # poupança, no ritmo de 1600/mês
            ],
            targets=ALL_TARGETS,
            income="8000",
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 10))

    assert not any(n.type == "negative_projection" for n in pending)


async def test_saving_a_lot_does_not_trigger_risk(monkeypatch):
    """Guardar dinheiro é o objetivo do app — não pode virar alerta vermelho."""
    install(
        monkeypatch,
        build_db(
            transactions=[tx("1000", 1), tx("5000", 3)],
            targets=ALL_TARGETS,
            income="8000",
        ),
    )

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 10))

    assert not any(n.type == "negative_projection" for n in pending)


async def test_no_alerts_at_all_without_income(monkeypatch):
    install(monkeypatch, build_db(transactions=[tx("9999", 1)], targets=[], income=None))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 20))

    assert pending == []


# --------------------------------------------------------------------------
# Fechamento de mês (goal_hit)
# --------------------------------------------------------------------------


async def test_goal_hit_for_bucket_that_stayed_within_the_ceiling(monkeypatch):
    install(monkeypatch, build_db(transactions=[tx("3000", 1)], targets=ALL_TARGETS))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 9, 1), closed=True)

    assert [n.subject for n in pending] == ["necessidades"]


async def test_no_goal_hit_for_bucket_that_blew_the_ceiling(monkeypatch):
    install(monkeypatch, build_db(transactions=[tx("5000", 1)], targets=ALL_TARGETS))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 9, 1), closed=True)

    assert pending == []


async def test_no_goal_hit_for_a_month_with_nothing_recorded(monkeypatch):
    """Parabenizar quem passou o mês sem abrir o app seria enganoso — não dá
    pra distinguir 'não gastou' de 'não registrou'."""
    install(monkeypatch, build_db(transactions=[], targets=ALL_TARGETS))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 9, 1), closed=True)

    assert pending == []


async def test_savings_goal_hit_requires_reaching_the_target(monkeypatch):
    install(monkeypatch, build_db(transactions=[tx("1000", 3)], targets=ALL_TARGETS))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 9, 1), closed=True)

    assert not any(n.subject == "poupanca" for n in pending)


async def test_savings_goal_hit_when_target_is_reached(monkeypatch):
    install(monkeypatch, build_db(transactions=[tx("1600", 3)], targets=ALL_TARGETS))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 9, 1), closed=True)

    assert any(n.subject == "poupanca" for n in pending)


async def test_closed_month_does_not_emit_risk_alerts(monkeypatch):
    install(monkeypatch, build_db(transactions=[tx("9000", 1)], targets=ALL_TARGETS))

    pending = await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 9, 1), closed=True)

    assert not any(n.type in ("budget_ceiling", "negative_projection") for n in pending)


# --------------------------------------------------------------------------
# Idempotência
# --------------------------------------------------------------------------


async def test_reevaluating_updates_instead_of_duplicating(monkeypatch):
    db = install(
        monkeypatch,
        build_db(
            transactions=[tx("3800", 1)],
            targets=[target("necessidades", "4000")],
        ),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))
    first_message = db.rows("notifications")[0]["message"]

    db.rows("transactions").append(tx("100", 1))
    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 6))

    assert len(db.rows("notifications")) == 1
    assert db.rows("notifications")[0]["message"] != first_message


async def test_a_read_alert_does_not_block_a_new_one(monkeypatch):
    db = install(
        monkeypatch,
        build_db(
            transactions=[tx("3800", 1)],
            targets=[target("necessidades", "4000")],
            notifications=[
                {
                    "id": 1,
                    "user_id": "user-1",
                    "type": "budget_ceiling",
                    "reference_month": "2026-08-01",
                    "subject": "necessidades",
                    "read": True,
                    "severity": "warning",
                    "title": "antigo",
                    "message": "antigo",
                }
            ],
        ),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    assert len(db.rows("notifications")) == 2


async def test_stale_alert_is_dropped_after_the_user_fixes_the_value(monkeypatch):
    """Digitou 3900 em vez de 390, o alerta nasceu; ao corrigir, o alerta não
    pode continuar na tela dizendo que ele está em 98% do limite."""
    db = install(
        monkeypatch,
        build_db(transactions=[tx("3900", 1)], targets=ALL_TARGETS),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))
    assert len(db.rows("notifications")) == 1

    db.rows("transactions").clear()
    db.rows("transactions").append(tx("390", 1))
    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    assert db.rows("notifications") == []


async def test_dismissal_does_not_touch_alerts_of_other_months(monkeypatch):
    db = install(
        monkeypatch,
        build_db(
            transactions=[],
            targets=ALL_TARGETS,
            notifications=[
                {
                    "id": 1,
                    "user_id": "user-1",
                    "type": "budget_ceiling",
                    "reference_month": "2026-07-01",
                    "subject": "necessidades",
                    "read": False,
                    "severity": "warning",
                    "title": "julho",
                    "message": "julho",
                }
            ],
        ),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 20))

    assert len(db.rows("notifications")) == 1


async def test_dismissal_keeps_goal_hit(monkeypatch):
    """goal_hit é conquista registrada, não estado que deixa de valer."""
    db = install(
        monkeypatch,
        build_db(
            transactions=[],
            targets=ALL_TARGETS,
            notifications=[
                {
                    "id": 1,
                    "user_id": "user-1",
                    "type": "goal_hit",
                    "reference_month": "2026-08-01",
                    "subject": "desejos",
                    "read": False,
                    "severity": "success",
                    "title": "meta",
                    "message": "meta",
                }
            ],
        ),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 20))

    assert len(db.rows("notifications")) == 1


async def test_insert_failure_other_than_duplicate_is_not_swallowed(monkeypatch):
    """Migration não aplicada não pode virar log de 'já existia' — o motor
    ficaria sem efeito e nada apareceria como quebrado."""
    from postgrest.exceptions import APIError

    db = install(monkeypatch, build_db(transactions=[tx("3800", 1)], targets=ALL_TARGETS))

    original_execute = db.execute

    def fail_on_notification_insert(q):
        if q.table == "notifications" and q.op == "insert":
            raise APIError({"code": "42703", "message": "column reference_month does not exist"})
        return original_execute(q)

    monkeypatch.setattr(db, "execute", fail_on_notification_insert)

    with pytest.raises(APIError):
        await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))


async def test_duplicate_insert_is_tolerated(monkeypatch):
    from postgrest.exceptions import APIError

    db = install(monkeypatch, build_db(transactions=[tx("3800", 1)], targets=ALL_TARGETS))

    original_execute = db.execute

    def fail_on_notification_insert(q):
        if q.table == "notifications" and q.op == "insert":
            raise APIError({"code": "23505", "message": "duplicate key"})
        return original_execute(q)

    monkeypatch.setattr(db, "execute", fail_on_notification_insert)

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))


async def test_alert_goes_to_every_household_member(monkeypatch):
    db = install(
        monkeypatch,
        build_db(
            transactions=[tx("3800", 1)],
            targets=[target("necessidades", "4000")],
            household_members=[
                {"household_id": HOUSEHOLD, "user_id": "user-1"},
                {"household_id": HOUSEHOLD, "user_id": "user-2"},
            ],
        ),
    )

    await engine.evaluate_month(HOUSEHOLD, AUGUST, today=date(2026, 8, 5))

    assert {row["user_id"] for row in db.rows("notifications")} == {"user-1", "user-2"}


# --------------------------------------------------------------------------
# Gatilhos
# --------------------------------------------------------------------------


async def test_event_trigger_never_raises(monkeypatch):
    """Roda em background depois da resposta: não pode derrubar nada."""

    async def boom(*_args, **_kwargs):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(engine, "evaluate_month", boom)

    await engine.evaluate_after_transaction(HOUSEHOLD, "2026-08-05")


async def test_event_trigger_ignores_malformed_date(monkeypatch):
    calls = []

    async def record(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(engine, "evaluate_month", record)

    await engine.evaluate_after_transaction(HOUSEHOLD, "nao-e-data")

    assert calls == []


async def test_daily_trigger_closes_previous_month_on_the_first(monkeypatch):
    calls = []

    async def record(household_id, month_start, today=None, closed=False):
        calls.append((month_start, closed))

    monkeypatch.setattr(engine, "evaluate_month", record)

    await engine.evaluate_daily(HOUSEHOLD, today=date(2026, 8, 1))

    assert (date(2026, 8, 1), False) in calls
    assert (date(2026, 7, 1), True) in calls


async def test_daily_trigger_only_current_month_on_other_days(monkeypatch):
    calls = []

    async def record(household_id, month_start, today=None, closed=False):
        calls.append((month_start, closed))

    monkeypatch.setattr(engine, "evaluate_month", record)

    await engine.evaluate_daily(HOUSEHOLD, today=date(2026, 8, 15))

    assert calls == [(date(2026, 8, 1), False)]


async def test_daily_trigger_rolls_over_to_december(monkeypatch):
    calls = []

    async def record(household_id, month_start, today=None, closed=False):
        calls.append((month_start, closed))

    monkeypatch.setattr(engine, "evaluate_month", record)

    await engine.evaluate_daily(HOUSEHOLD, today=date(2027, 1, 1))

    assert (date(2026, 12, 1), True) in calls
