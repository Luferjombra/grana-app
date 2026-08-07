from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator

TRANSACTION_TYPES = ("expense", "income", "transfer")


class TransactionCreate(BaseModel):
    amount: Decimal
    # Obrigatório pra despesa (specs/09): sem categoria a transação não cai em
    # nenhum bucket e ficaria invisível pra regra 50-30-20 — ver validador
    # abaixo. Receita/transferência não entram no cálculo de bucket.
    category_id: int | None = None
    type: str
    occurred_at: str
    merchant: str | None = None
    note: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal) -> Decimal:
        # O sinal vem de `type`, não do valor — guardar despesa como negativa
        # duplicaria a semântica e quebraria as somas do dashboard.
        if value <= 0:
            raise ValueError("O valor precisa ser maior que zero.")
        return value

    @field_validator("type")
    @classmethod
    def type_must_be_valid(cls, value: str) -> str:
        if value not in TRANSACTION_TYPES:
            raise ValueError(f"Tipo inválido. Use um de: {', '.join(TRANSACTION_TYPES)}.")
        return value

    @model_validator(mode="after")
    def expense_requires_category(self):
        if self.type == "expense" and self.category_id is None:
            raise ValueError("Despesa precisa de uma categoria.")
        return self

    @model_validator(mode="after")
    def installments_must_be_coherent(self):
        number, total = self.installment_number, self.installment_total
        if (number is None) != (total is None):
            raise ValueError("Informe parcela atual e total de parcelas juntos.")
        if number is not None:
            if number < 1 or total < 1:
                raise ValueError("Parcelas precisam ser maiores que zero.")
            if number > total:
                raise ValueError("A parcela atual não pode ser maior que o total.")
        return self


class TransactionUpdate(BaseModel):
    amount: Decimal | None = None
    category_id: int | None = None
    type: str | None = None
    occurred_at: str | None = None
    merchant: str | None = None
    note: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("O valor precisa ser maior que zero.")
        return value

    @field_validator("type")
    @classmethod
    def type_must_be_valid(cls, value: str | None) -> str | None:
        if value is not None and value not in TRANSACTION_TYPES:
            raise ValueError(f"Tipo inválido. Use um de: {', '.join(TRANSACTION_TYPES)}.")
        return value
