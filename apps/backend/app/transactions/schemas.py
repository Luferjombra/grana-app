from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator

TRANSACTION_TYPES = ("expense", "income", "transfer")

# Teto do parcelamento — cada parcela vira uma linha, então um número solto
# aqui viraria centenas de transações num único POST.
MAX_INSTALLMENTS = 12


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
    # Só o total de parcelas é informado: o `amount` é o valor **cheio** da
    # compra e o backend gera uma transação por parcela, numerando-as. Aceitar
    # installment_number aqui deixaria o cliente criar parcelas soltas, sem as
    # irmãs — foi assim que a primeira versão perdia 11 de 12 parcelas.
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
        total = self.installment_total
        if total is None:
            return self
        if total < 1:
            raise ValueError("O total de parcelas precisa ser pelo menos 1.")
        if total > MAX_INSTALLMENTS:
            raise ValueError(f"No máximo {MAX_INSTALLMENTS} parcelas.")
        if self.type != "expense":
            raise ValueError("Só despesa pode ser parcelada.")
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
