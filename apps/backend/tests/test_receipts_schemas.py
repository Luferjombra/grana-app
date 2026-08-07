import pytest
from pydantic import ValidationError

from app.receipts.schemas import ReceiptConfirm


def make(**overrides):
    payload = {"amount": "42.50", "category_id": 1, "occurred_at": "2026-08-05"}
    payload.update(overrides)
    return ReceiptConfirm(**payload)


def test_accepts_valid_payload():
    confirm = make(merchant="Mercado")
    assert str(confirm.amount) == "42.50"
    assert confirm.occurred_at == "2026-08-05"


@pytest.mark.parametrize("value", ["05/08/2026", "2026-8-5", "ontem", "", "2026-02-31"])
def test_rejects_non_iso_date(value):
    """O caminho manual já validava; sem isso aqui, data em formato brasileiro
    virava erro do Postgres em vez de 422 explicativo."""
    with pytest.raises(ValidationError):
        make(occurred_at=value)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_rejects_non_positive_amount(value):
    with pytest.raises(ValidationError):
        make(amount=value)


def test_ignores_installments_from_the_client():
    """Recibo não parcela: aceitar o total sem expandir em N transações
    gravaria só a primeira parcela e deixaria os meses seguintes livres."""
    confirm = make(installment_total=12, installment_number=1)
    assert not hasattr(confirm, "installment_total")
    assert not hasattr(confirm, "installment_number")
