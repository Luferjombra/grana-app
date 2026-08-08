from datetime import date
from decimal import Decimal

import pytest

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.gamification import service
from app.gamification.rules import (
    RESULT_XP_POOL,
    XP_PER_ACTIVE_DAY,
    XP_PER_LEVEL,
    active_days_from,
    buckets_met,
    habit_xp,
    level_for,
    result_xp,
    roundup_of,
    xp_into_level,
)
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)
TODAY = date(2026, 8, 20)
RULE = {"necessidades_pct": 50, "desejos_pct": 30, "poupanca_pct": 20}

BUCKET_OF = {1: "necessidades", 2: "desejos", 3: "poupanca"}


def tx(day: int, amount: str, category_id: int = 1, created_day: int | None = None, **over):
    bucket = BUCKET_OF.get(category_id)
    row = {
        "id": over.pop("id", day * 100 + category_id),
        "household_id": 42,
        "amount": amount,
        "type": "expense",
        "occurred_at": f"2026-08-{day:02d}",
        "created_at": f"2026-08-{(created_day or day):02d}T10:00:00+00:00",
        "entry_method": "manual",
        "category_id": category_id,
        "categories": {"id": category_id, "name": bucket, "bucket": bucket, "icon": None},
    }
    row.update(over)
    return row


def install(monkeypatch, db, targets: dict[str, str] | None = None):
    monkeypatch.setattr(service, "get_db", lambda: db)
    monkeypatch.setattr(service, "today_local", lambda: TODAY)

    async def rule(household_id):
        return dict(RULE)

    async def ensure(household_id, month_start):
        return {k: Decimal(v) for k, v in (targets or {}).items()}

    monkeypatch.setattr(targets_module, "get_budget_rule", rule)
    monkeypatch.setattr(targets_module, "ensure_month_targets", ensure)
    return db


# --------------------------------------------------------------------------
# A regra pura
# --------------------------------------------------------------------------


def test_active_days_counts_the_day_the_app_was_used_once():
    """O ponto central da regra: 30 lançamentos no mesmo dia valem 1 dia ativo.

    Sem isso, quem compra 30 cafés ganharia dez vezes mais XP que quem compra 3, e
    o app celebraria quem gasta mais — o mecanismo pelo qual a Robinhood foi
    processada.
    """
    mesmo_dia = [f"2026-08-05T{h:02d}:00:00+00:00" for h in range(10, 20)]

    assert active_days_from(mesmo_dia) == 1
    assert habit_xp(active_days_from(mesmo_dia)) == XP_PER_ACTIVE_DAY


def test_import_of_a_whole_year_counts_as_one_active_day():
    """Import de extrato cria centenas de linhas no mesmo instante. Se o dia ativo
    viesse de `occurred_at`, isso daria ~30 dias de uma vez."""
    import_inteiro = ["2026-08-20T14:00:00+00:00"] * 1059

    assert active_days_from(import_inteiro) == 1


def test_habit_xp_is_linear_and_capped_by_the_calendar():
    # 30 dias × 10 = 300, que é de propósito igual ao pool de resultado
    assert habit_xp(30) == RESULT_XP_POOL
    assert habit_xp(0) == 0
    assert habit_xp(-5) == 0


def test_ceiling_bucket_needs_spending_above_zero():
    """Mesma leitura do goal_hit da spec 07: não dá pra distinguir "não gastou" de
    "não registrou", e premiar quem não abriu o app seria enganoso."""
    targets = {"necessidades": Decimal("4000")}

    assert buckets_met({"necessidades": Decimal("3000")}, targets) == ["necessidades"]
    assert buckets_met({"necessidades": Decimal("0")}, targets) == []


def test_ceiling_bucket_over_target_does_not_count():
    assert buckets_met({"desejos": Decimal("2500")}, {"desejos": Decimal("2400")}) == []


def test_savings_is_a_goal_not_a_ceiling():
    """Poupança inverte: cumprir é chegar lá, e passar também vale."""
    targets = {"poupanca": Decimal("1600")}

    assert buckets_met({"poupanca": Decimal("1600")}, targets) == ["poupanca"]
    assert buckets_met({"poupanca": Decimal("2000")}, targets) == ["poupanca"]
    assert buckets_met({"poupanca": Decimal("1500")}, targets) == []


def test_result_xp_uses_the_household_weights():
    """Reusa os percentuais 50-30-20 vigentes: se o usuário editar, o XP acompanha
    sem código novo."""
    assert result_xp(["necessidades"], RULE) == 150  # 300 × 50%
    assert result_xp(["desejos"], RULE) == 90  # 300 × 30%
    assert result_xp(["poupanca"], RULE) == 60  # 300 × 20%
    assert result_xp(["necessidades", "desejos", "poupanca"], RULE) == RESULT_XP_POOL
    assert result_xp([], RULE) == 0


def test_result_xp_follows_edited_percentages():
    editado = {"necessidades_pct": 60, "desejos_pct": 20, "poupanca_pct": 20}

    assert result_xp(["necessidades"], editado) == 180


def test_perfect_month_is_exactly_one_level():
    """Um nível por mês perfeito é a única curva que dá pra explicar numa frase."""
    perfeito = habit_xp(30) + result_xp(["necessidades", "desejos", "poupanca"], RULE)

    assert perfeito == XP_PER_LEVEL
    assert level_for(perfeito) == 2


def test_level_starts_at_one():
    """Ninguém entra no app em nível zero."""
    assert level_for(0) == 1
    assert level_for(-10) == 1
    assert xp_into_level(0) == (0, XP_PER_LEVEL)


def test_roundup_of_a_whole_amount_is_zero():
    """Cobrar arredondamento de quem gastou R$ 20,00 exatos seria inventar
    despesa."""
    assert roundup_of(Decimal("20.00")) == Decimal("0.00")
    assert roundup_of(Decimal("19.01")) == Decimal("0.99")
    assert roundup_of(Decimal("19.99")) == Decimal("0.01")
    assert roundup_of(Decimal("0")) == Decimal("0.00")


# --------------------------------------------------------------------------
# Progresso
# --------------------------------------------------------------------------


async def test_progress_counts_distinct_days_not_transactions(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            {
                "transactions": [
                    tx(5, "10.00"),
                    tx(5, "20.00", id=999),  # mesmo dia
                    tx(6, "30.00"),
                ],
                "roundup_savings": [],
            }
        ),
    )

    result = await service.get_progress(USER)

    assert result["active_days"] == 2
    assert result["total_xp"] == 20
    assert result["level"] == 1


async def test_progress_adds_result_xp_for_buckets_met(monkeypatch):
    install(
        monkeypatch,
        FakeDb({"transactions": [tx(5, "3000.00", category_id=1)], "roundup_savings": []}),
        targets={"necessidades": "4000"},
    )

    result = await service.get_progress(USER)
    by_source = {entry["source"]: entry["xp"] for entry in result["breakdown"]}

    assert by_source["habito"] == 10
    assert by_source["resultado"] == 150
    assert result["total_xp"] == 160


async def test_progress_without_income_gives_only_habit_xp(monkeypatch):
    """Sem renda não há teto, então não há resultado a premiar — mas o hábito
    continua valendo, que é o que sustenta quem acabou de instalar."""
    install(
        monkeypatch,
        FakeDb({"transactions": [tx(5, "100.00")], "roundup_savings": []}),
        targets=None,
    )

    result = await service.get_progress(USER)

    assert result["total_xp"] == 10
    assert result["breakdown"][1]["xp"] == 0


async def test_progress_with_no_transactions_is_level_one_not_an_error(monkeypatch):
    install(monkeypatch, FakeDb({"transactions": [], "roundup_savings": []}))

    result = await service.get_progress(USER)

    assert result["total_xp"] == 0
    assert result["level"] == 1
    assert result["active_days"] == 0


async def test_progress_ignores_another_household(monkeypatch):
    outro = tx(5, "100.00")
    outro["household_id"] = 99
    install(monkeypatch, FakeDb({"transactions": [outro], "roundup_savings": []}))

    result = await service.get_progress(USER)

    assert result["active_days"] == 0


# --------------------------------------------------------------------------
# Conquistas
# --------------------------------------------------------------------------


async def test_achievements_unlock_from_real_data(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            {
                "transactions": [tx(day, "10.00", created_day=day) for day in range(1, 9)]
                + [tx(9, "50.00", entry_method="receipt_ocr", created_day=9)],
                "roundup_savings": [],
            }
        ),
    )

    result = await service.get_achievements(USER)
    unlocked = {item["code"] for item in result["items"] if item["unlocked"]}

    assert "first_entry" in unlocked
    assert "active_7" in unlocked  # 9 dias distintos
    assert "used_receipt" in unlocked
    assert "active_21" not in unlocked
    assert "used_import" not in unlocked
    assert result["total"] == len(service.ACHIEVEMENTS)


async def test_reserve_achievements_come_from_the_reserve(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            {
                "transactions": [],
                "roundup_savings": [],
                "emergency_reserve": [
                    {
                        "household_id": 42,
                        "essential_expenses_baseline": "4000.00",
                        "current_balance": "12000.00",
                        "months_multiplier": 6,
                    }
                ],
            }
        ),
    )

    result = await service.get_achievements(USER)
    unlocked = {item["code"] for item in result["items"] if item["unlocked"]}

    assert "reserve_1" in unlocked
    assert "reserve_3" in unlocked  # 12.000 / 4.000 = 3 meses
    assert "reserve_full" not in unlocked  # alvo é 24.000


async def test_achievements_do_not_break_without_a_reserve(monkeypatch):
    install(monkeypatch, FakeDb({"transactions": [], "roundup_savings": []}))

    result = await service.get_achievements(USER)

    assert result["unlocked_count"] == 0


# --------------------------------------------------------------------------
# Cofrinho
# --------------------------------------------------------------------------


async def test_roundup_accumulates_the_change_of_each_expense(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            {
                "transactions": [tx(5, "19.01"), tx(6, "12.50"), tx(7, "8.00")],
                "roundup_savings": [],
            }
        ),
    )

    result = await service.get_roundup(USER)

    # 0.99 + 0.50 + 0.00
    assert result["accumulated"] == "1.49"
    assert result["transferred"] == "0.00"
    assert result["automatic"] is False


async def test_roundup_excludes_income(monkeypatch):
    install(
        monkeypatch,
        FakeDb(
            {
                "transactions": [tx(5, "19.01"), tx(6, "8000.50", type="income")],
                "roundup_savings": [],
            }
        ),
    )

    result = await service.get_roundup(USER)

    assert result["accumulated"] == "0.99"


async def test_transfer_records_the_ledger_and_does_not_repeat(monkeypatch):
    """Transferir duas vezes não pode contar o mesmo troco duas vezes."""
    db = install(
        monkeypatch,
        FakeDb(
            {
                "transactions": [tx(5, "19.01"), tx(6, "12.50")],
                "roundup_savings": [],
            }
        ),
    )

    first = await service.transfer_roundup(USER)
    assert first["transferred"] == "1.49"
    assert first["count"] == 2

    second = await service.transfer_roundup(USER)
    assert second["count"] == 0
    assert len(db.rows("roundup_savings")) == 2

    after = await service.get_roundup(USER)
    assert after["accumulated"] == "0.00"
    assert after["transferred"] == "1.49"


async def test_transfer_skips_whole_amounts(monkeypatch):
    db = install(
        monkeypatch,
        FakeDb({"transactions": [tx(5, "20.00"), tx(6, "30.00")], "roundup_savings": []}),
    )

    result = await service.transfer_roundup(USER)

    assert result["count"] == 0
    assert db.rows("roundup_savings") == []


@pytest.mark.parametrize("amount", ["0.01", "0.99", "1.00", "1234.56"])
def test_roundup_never_exceeds_one_real(amount):
    assert roundup_of(Decimal(amount)) < Decimal("1.00")


async def test_active_day_follows_when_the_app_was_used_not_when_the_money_was_spent(
    monkeypatch,
):
    """Importar o extrato de julho no dia 20 de agosto é uso do app em AGOSTO.

    Contar dia ativo pelo `occurred_at` erra nos dois sentidos: não daria XP em
    agosto, quando a pessoa de fato abriu o app, e daria um dia ativo retroativo a
    julho, que já passou. Este teste falha se alguém voltar a contar pelo
    `occurred_at` — o fixture dos outros testes tem as duas datas alinhadas e não
    pegaria isso.
    """
    importado = {
        "id": 5001,
        "household_id": 42,
        "amount": "150.00",
        "type": "expense",
        "occurred_at": "2026-07-15",  # gasto de julho
        "created_at": "2026-08-20T14:00:00+00:00",  # registrado em agosto
        "entry_method": "csv_import",
        "category_id": 1,
        "categories": {"id": 1, "name": "necessidades", "bucket": "necessidades", "icon": None},
    }
    install(monkeypatch, FakeDb({"transactions": [importado], "roundup_savings": []}))

    result = await service.get_progress(USER)

    assert result["active_days"] == 1
    assert result["total_xp"] == XP_PER_ACTIVE_DAY


async def test_roundup_reads_only_the_ledger_of_the_month(monkeypatch):
    """O livro é consultado pelos ids do mês, não inteiro: puxar todo o histórico
    do usuário cresceria sem teto."""
    db = install(
        monkeypatch,
        FakeDb({"transactions": [tx(5, "19.01")], "roundup_savings": []}),
    )

    await service.get_roundup(USER)

    reads = [q for q in db.queries if q.table == "roundup_savings"]
    assert len(reads) == 1
    assert "transaction_id__in" in reads[0].filters
