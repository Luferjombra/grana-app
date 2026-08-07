import pytest
from pydantic import ValidationError

from app.budget.schemas import BudgetRuleUpdate
from app.transactions.schemas import TransactionCreate


def make_transaction(**overrides):
    payload = {
        "amount": "10.00",
        "type": "expense",
        "occurred_at": "2026-08-05",
        "category_id": 1,
    }
    payload.update(overrides)
    return TransactionCreate(**payload)


def test_transaction_accepts_valid_payload():
    transaction = make_transaction(category_id=1, merchant="Mercado")
    assert str(transaction.amount) == "10.00"


@pytest.mark.parametrize("amount", ["0", "-1", "-0.01"])
def test_transaction_rejects_non_positive_amount(amount):
    with pytest.raises(ValidationError):
        make_transaction(amount=amount)


def test_transaction_rejects_unknown_type():
    with pytest.raises(ValidationError):
        make_transaction(type="estorno")


def test_expense_requires_a_category():
    """Sem categoria a despesa não cai em bucket nenhum e escaparia da
    regra 50-30-20 (specs/09 lista category_id como obrigatório)."""
    with pytest.raises(ValidationError):
        make_transaction(type="expense", category_id=None)


def test_income_does_not_require_a_category():
    transaction = make_transaction(type="income", category_id=None)
    assert transaction.category_id is None


def test_transaction_ignores_installment_number_from_the_client():
    """Só o total é aceito: o número de cada parcela é atribuído pelo backend
    ao gerar a série. Aceitar do cliente permitiria criar parcela solta."""
    transaction = make_transaction(installment_number=7, installment_total=3)
    assert not hasattr(transaction, "installment_number")
    assert transaction.installment_total == 3


def test_transaction_rejects_zero_installments():
    with pytest.raises(ValidationError):
        make_transaction(installment_total=0)


def test_transaction_accepts_installment_total():
    transaction = make_transaction(installment_total=12)
    assert transaction.installment_total == 12


def test_budget_rule_accepts_sum_of_100():
    rule = BudgetRuleUpdate(necessidades_pct="60", desejos_pct="20", poupanca_pct="20")
    assert str(rule.necessidades_pct) == "60"


@pytest.mark.parametrize(
    "values",
    [
        ("50", "30", "10"),
        ("50", "30", "30"),
        ("100", "1", "0"),
    ],
)
def test_budget_rule_rejects_sum_other_than_100(values):
    with pytest.raises(ValidationError):
        BudgetRuleUpdate(necessidades_pct=values[0], desejos_pct=values[1], poupanca_pct=values[2])


def test_budget_rule_rejects_negative_percentage():
    with pytest.raises(ValidationError):
        BudgetRuleUpdate(necessidades_pct="120", desejos_pct="-20", poupanca_pct="0")
