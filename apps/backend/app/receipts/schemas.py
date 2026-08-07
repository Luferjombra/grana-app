from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator


class ReceiptConfirm(BaseModel):
    """Campos extraídos pelo OCR, confirmados (ou editados) pelo usuário
    antes de virarem uma transaction de verdade — specs/05.

    Sem campos de parcelamento de propósito: parcelar exige gerar uma
    transação por mês (ver transactions/service.py), e aceitar o total aqui
    sem essa expansão gravaria só a primeira parcela, deixando os meses
    seguintes falsamente livres. Quando recibo parcelado virar requisito,
    reusar a mesma expansão em vez de duplicar a regra.
    """

    amount: Decimal
    category_id: int
    occurred_at: str
    merchant: str | None = None
    note: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("O valor precisa ser maior que zero.")
        return value

    @field_validator("occurred_at")
    @classmethod
    def date_must_be_iso(cls, value: str) -> str:
        # O caminho manual já validava; sem isso aqui, uma data em formato
        # brasileiro viraria erro do Postgres em vez de 422 explicativo.
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ValueError("Data inválida. Use o formato AAAA-MM-DD.") from exc
