from datetime import date
from decimal import Decimal

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.insights import service
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)
TODAY = date(2026, 8, 15)

BUCKETS_BY_CATEGORY = {
    1: ("Mercado", "necessidades"),
    2: ("Moradia", "necessidades"),
    3: ("Delivery", "desejos"),
    4: ("Streaming", "desejos"),
    5: ("Investimentos", "poupanca"),
}


def tx(occurred_at: str, amount: str, category_id: int | None = 1, **over):
    name, bucket = BUCKETS_BY_CATEGORY.get(category_id, (None, None))
    row = {
        "id": over.pop("id", None) or abs(hash(occurred_at + amount)) % 100000,
        "household_id": 42,
        "amount": amount,
        "type": "expense",
        "occurred_at": occurred_at,
        "merchant": "LOJA",
        "category_id": category_id,
        "categories": (
            {"id": category_id, "name": name, "bucket": bucket, "icon": None}
            if category_id
            else None
        ),
    }
    row.update(over)
    return row


def install(monkeypatch, rows):
    db = FakeDb({"transactions": list(rows)})
    monkeypatch.setattr(service, "get_db", lambda: db)
    monkeypatch.setattr(service, "today_local", lambda: TODAY)
    return db


# --------------------------------------------------------------------------
# Mês contra mês
# --------------------------------------------------------------------------


async def test_month_over_month_cuts_both_months_at_the_same_day(monkeypatch):
    """A mentira mais fácil de contar com esses dados: comparar 15 dias de agosto
    contra 31 de julho e anunciar economia."""
    install(
        monkeypatch,
        [
            tx("2026-08-05", "100.00"),
            tx("2026-08-10", "100.00"),
            # depois do dia 15: fora dos dois lados da conta
            tx("2026-07-05", "100.00"),
            tx("2026-07-10", "100.00"),
            tx("2026-07-25", "900.00"),
        ],
    )

    result = await service.month_over_month(USER, date(2026, 8, 1))

    assert result["partial"] is True
    assert result["comparable_days"] == 15
    assert result["total"]["current"] == "200.00"
    # 900 do dia 25 de julho não entra: seria comparar contra mês inteiro
    assert result["total"]["previous"] == "200.00"
    assert result["total"]["direction"] == "flat"


async def test_month_over_month_compares_closed_months_whole(monkeypatch):
    install(
        monkeypatch,
        [tx("2026-06-25", "900.00"), tx("2026-05-25", "300.00")],
    )

    result = await service.month_over_month(USER, date(2026, 6, 1))

    assert result["partial"] is False
    assert result["comparable_days"] is None
    assert result["total"]["current"] == "900.00"
    assert result["total"]["delta"] == "600.00"
    assert result["total"]["delta_pct"] == "200.0"


async def test_delta_pct_is_null_when_previous_was_zero(monkeypatch):
    """Dividir por zero não tem resposta, e "aumento de 100%" a partir de nada
    seria invenção."""
    install(monkeypatch, [tx("2026-06-10", "500.00")])

    result = await service.month_over_month(USER, date(2026, 6, 1))

    assert result["total"]["previous"] == "0.00"
    assert result["total"]["delta_pct"] is None
    assert result["total"]["direction"] == "up"


async def test_month_over_month_excludes_savings(monkeypatch):
    """Aporte é a saída planejada dando certo, não consumo (specs/07)."""
    install(monkeypatch, [tx("2026-06-10", "500.00"), tx("2026-06-11", "2000.00", category_id=5)])

    result = await service.month_over_month(USER, date(2026, 6, 1))

    assert result["total"]["current"] == "500.00"
    assert [b["bucket"] for b in result["by_bucket"]] == ["necessidades", "desejos"]


async def test_category_movers_are_ordered_by_amount_not_percent(monkeypatch):
    """200% de aumento em algo de R$ 3 não é notícia; R$ 400 a mais no mercado é."""
    install(
        monkeypatch,
        [
            tx("2026-06-10", "500.00", category_id=1),  # mercado: +400
            tx("2026-06-11", "9.00", category_id=3),  # delivery: +6 (200%)
            tx("2026-05-10", "100.00", category_id=1),
            tx("2026-05-11", "3.00", category_id=3),
        ],
    )

    result = await service.month_over_month(USER, date(2026, 6, 1))

    assert result["by_category"][0]["name"] == "Mercado"
    assert result["by_category"][0]["delta"] == "400.00"


async def test_uncategorized_shows_up_as_its_own_mover(monkeypatch):
    install(monkeypatch, [tx("2026-06-10", "80.00", category_id=None)])

    result = await service.month_over_month(USER, date(2026, 6, 1))

    assert result["by_category"][0]["name"] == "Sem categoria"


# --------------------------------------------------------------------------
# Assinaturas
# --------------------------------------------------------------------------


def sub(month: str, amount: str, merchant: str):
    return tx(f"2026-{month}-10", amount, category_id=4, merchant=merchant)


async def test_detects_a_subscription_seen_in_three_months(monkeypatch):
    install(
        monkeypatch,
        [
            sub("06", "44.90", "NETFLIX.COM 1234"),
            sub("07", "44.90", "NETFLIX.COM 5678"),
            sub("08", "44.90", "NETFLIX.COM 9012"),
        ],
    )

    result = await service.recurring_subscriptions(USER)

    assert len(result["items"]) == 1
    # merchant_key descarta o número do descritor: é o mesmo comerciante
    assert result["items"][0]["months_seen"] == 3
    assert result["items"][0]["amount"] == "44.90"
    assert result["monthly_total"] == "44.90"


async def test_two_months_is_not_a_subscription(monkeypatch):
    install(monkeypatch, [sub("07", "44.90", "NETFLIX"), sub("08", "44.90", "NETFLIX")])

    result = await service.recurring_subscriptions(USER)

    assert result["items"] == []


async def test_ignores_a_merchant_with_unstable_amounts(monkeypatch):
    """Sem essa checagem, o supermercado visitado todo mês entraria na lista como
    se fosse mensalidade."""
    install(
        monkeypatch,
        [
            sub("06", "150.00", "SUPERMERCADO"),
            sub("07", "480.00", "SUPERMERCADO"),
            sub("08", "220.00", "SUPERMERCADO"),
        ],
    )

    result = await service.recurring_subscriptions(USER)

    assert result["items"] == []


async def test_accepts_a_small_price_increase(monkeypatch):
    """Assinatura reajusta, e cobrança em dólar varia com o câmbio."""
    install(
        monkeypatch,
        [
            sub("06", "44.90", "SPOTIFY"),
            sub("07", "44.90", "SPOTIFY"),
            sub("08", "47.90", "SPOTIFY"),
        ],
    )

    result = await service.recurring_subscriptions(USER)

    assert len(result["items"]) == 1


async def test_cancelled_subscription_is_listed_but_not_counted(monkeypatch):
    """Cancelada continuaria "ativa" na tela e inflaria o custo fixo mensal."""
    install(
        monkeypatch,
        [
            sub("03", "30.00", "REVISTA"),
            sub("04", "30.00", "REVISTA"),
            sub("05", "30.00", "REVISTA"),
            sub("07", "44.90", "NETFLIX"),
            sub("08", "44.90", "NETFLIX"),
            sub("06", "44.90", "NETFLIX"),
        ],
    )

    result = await service.recurring_subscriptions(USER)
    by_label = {item["label"]: item for item in result["items"]}

    assert by_label["REVISTA"]["active"] is False
    assert by_label["NETFLIX"]["active"] is True
    assert result["monthly_total"] == "44.90"


async def test_subscription_ignores_transaction_without_merchant(monkeypatch):
    install(
        monkeypatch,
        [
            tx("2026-06-10", "50.00", merchant=None),
            tx("2026-07-10", "50.00", merchant=""),
            tx("2026-08-10", "50.00", merchant="   "),
        ],
    )

    result = await service.recurring_subscriptions(USER)

    assert result["items"] == []


# --------------------------------------------------------------------------
# Maiores gastos
# --------------------------------------------------------------------------


async def test_top_transactions_orders_by_amount(monkeypatch):
    install(
        monkeypatch,
        [tx("2026-08-01", "10.00"), tx("2026-08-02", "900.00"), tx("2026-08-03", "50.00")],
    )

    result = await service.top_transactions(USER, date(2026, 8, 1), 2)

    assert [item["amount"] for item in result["items"]] == ["900.00", "50.00"]


async def test_top_transactions_reports_the_savings_it_excluded(monkeypatch):
    """Um aporte grande seria o "maior gasto" do mês e não é gasto — mas sumir
    com ele em silêncio faria o usuário procurar o lançamento que falta."""
    install(monkeypatch, [tx("2026-08-01", "100.00"), tx("2026-08-02", "5000.00", category_id=5)])

    result = await service.top_transactions(USER, date(2026, 8, 1), 5)

    assert [item["amount"] for item in result["items"]] == ["100.00"]
    assert result["excluded_savings"] == "5000.00"


async def test_top_transactions_clamps_a_silly_limit(monkeypatch):
    install(monkeypatch, [tx(f"2026-08-{day:02d}", f"{day}.00") for day in range(1, 11)])

    # limit 0 cai no default (5), em vez de devolver lista vazia
    zero = await service.top_transactions(USER, date(2026, 8, 1), 0)
    assert len(zero["items"]) == 5

    # limit absurdo é limitado ao teto, não repassado ao banco
    huge = await service.top_transactions(USER, date(2026, 8, 1), 99999)
    assert len(huge["items"]) == 10

    negative = await service.top_transactions(USER, date(2026, 8, 1), -3)
    assert len(negative["items"]) == 5


# --------------------------------------------------------------------------
# Média de três meses
# --------------------------------------------------------------------------


async def test_three_month_average_uses_closed_months(monkeypatch):
    install(
        monkeypatch,
        [
            tx("2026-08-10", "50.00"),  # mês corrente: não entra na média
            tx("2026-07-10", "300.00"),
            tx("2026-06-10", "600.00"),
            tx("2026-05-10", "300.00"),
        ],
    )

    result = await service.three_month_average(USER)

    assert result["months_used"] == ["2026-07", "2026-06", "2026-05"]
    assert result["average_total"] == "400.00"
    assert result["current_month"]["spent"] == "50.00"
    assert result["current_month"]["partial"] is True


async def test_average_skips_months_without_spending(monkeypatch):
    """Mês vazio quase sempre é "não registrei", não "não gastei" — incluí-lo
    como zero derrubaria a média e faria o mês corrente parecer um desastre."""
    install(monkeypatch, [tx("2026-07-10", "900.00")])

    result = await service.three_month_average(USER)

    # média de [900], não de [900, 0, 0] = 300
    assert result["months_used"] == ["2026-07"]
    assert result["average_total"] == "900.00"


async def test_average_without_any_history_is_null_not_zero(monkeypatch):
    install(monkeypatch, [])

    result = await service.three_month_average(USER)

    assert result["average_total"] is None
    assert result["months_used"] == []


# --------------------------------------------------------------------------
# Detalhe do health score
# --------------------------------------------------------------------------


def install_health(monkeypatch, spent: dict[str, str], targets: dict[str, str] | None):
    async def rule(household_id):
        return {"necessidades_pct": 50, "desejos_pct": 30, "poupanca_pct": 20}

    async def ensure(household_id, month_start):
        if targets is None:
            return {}
        return {bucket: Decimal(value) for bucket, value in targets.items()}

    async def fetch(household_id, month_start):
        return []

    def aggregate(rows):
        return targets_module.MonthTotals(
            income=Decimal("0"),
            expense=Decimal("0"),
            by_bucket={bucket: Decimal(value) for bucket, value in spent.items()},
            by_category={},
            uncategorized_expense=Decimal("77.00"),
        )

    monkeypatch.setattr(targets_module, "get_budget_rule", rule)
    monkeypatch.setattr(targets_module, "ensure_month_targets", ensure)
    monkeypatch.setattr(targets_module, "fetch_month_transactions", fetch)
    monkeypatch.setattr(targets_module, "aggregate_month", aggregate)


async def test_breakdown_marks_ceiling_and_goal(monkeypatch):
    """Teto vs meta muda a leitura: ficar abaixo é bom em desejos e é ficar
    devendo em poupança."""
    install_health(
        monkeypatch,
        spent={"necessidades": "4000", "desejos": "2400", "poupanca": "1600"},
        targets={"necessidades": "4000", "desejos": "2400", "poupanca": "1600"},
    )

    result = await service.health_score_breakdown(USER, date(2026, 8, 1))
    kinds = {entry["bucket"]: entry["kind"] for entry in result["breakdown"]}

    assert result["score"] == 100
    assert result["label"] == "saudavel"
    assert kinds == {"necessidades": "ceiling", "desejos": "ceiling", "poupanca": "goal"}


async def test_breakdown_without_income_explains_instead_of_failing(monkeypatch):
    """Sem renda não existe teto, e sem teto não há aderência a medir. Devolve
    200 com a razão: a tela precisa explicar, não errar."""
    install_health(monkeypatch, spent={"necessidades": "500"}, targets=None)

    result = await service.health_score_breakdown(USER, date(2026, 8, 1))

    assert result["score"] is None
    assert result["reason"] == "sem_renda"
    assert result["breakdown"] == []


async def test_breakdown_surfaces_uncategorized_expense(monkeypatch):
    """Despesa sem categoria não pontua e não pune, então o usuário precisa saber
    que a nota ignora esse valor."""
    install_health(
        monkeypatch,
        spent={"necessidades": "4000", "desejos": "2400", "poupanca": "1600"},
        targets={"necessidades": "4000", "desejos": "2400", "poupanca": "1600"},
    )

    result = await service.health_score_breakdown(USER, date(2026, 8, 1))

    assert result["uncategorized_expense"] == "77.00"


async def test_monthly_investment_is_not_a_subscription(monkeypatch):
    """Aporte de valor fixo passa em todos os testes de recorrência, mas entraria
    no `monthly_total` que a tela apresenta como custo fixo — e aporte não é
    custo (specs/07)."""
    install(
        monkeypatch,
        [
            tx("2026-06-05", "1000.00", category_id=5, merchant="APLICACAO CDB"),
            tx("2026-07-05", "1000.00", category_id=5, merchant="APLICACAO CDB"),
            tx("2026-08-05", "1000.00", category_id=5, merchant="APLICACAO CDB"),
        ],
    )

    result = await service.recurring_subscriptions(USER)

    assert result["items"] == []
    assert result["monthly_total"] == "0.00"
