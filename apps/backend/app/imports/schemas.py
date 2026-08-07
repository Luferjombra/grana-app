from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator

MAX_CONFIRM_ROWS = 2000


class ImportRow(BaseModel):
    """Linha confirmada pelo usuário no preview, já com categoria.

    O preview é stateless (specs/11): o cliente devolve as linhas aqui, e o
    backend revalida tudo — não confia no que voltou só porque ele mandou.
    """

    amount: Decimal
    type: str
    occurred_at: str
    description: str | None = None
    category_id: int | None = None
    external_id: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("O valor precisa ser maior que zero.")
        return value

    @field_validator("type")
    @classmethod
    def type_must_be_valid(cls, value: str) -> str:
        if value not in ("expense", "income"):
            raise ValueError("Extrato só gera despesa ou receita.")
        return value

    @model_validator(mode="after")
    def expense_requires_category(self):
        # Mesma regra do lançamento manual: despesa sem categoria escapa da
        # regra 50-30-20 e o health score fica otimista.
        if self.type == "expense" and self.category_id is None:
            raise ValueError("Despesa precisa de uma categoria.")
        return self


class ImportConfirm(BaseModel):
    rows: list[ImportRow]

    @field_validator("rows")
    @classmethod
    def rows_must_be_sane(cls, value: list[ImportRow]) -> list[ImportRow]:
        if not value:
            raise ValueError("Nenhuma linha para importar.")
        if len(value) > MAX_CONFIRM_ROWS:
            raise ValueError(f"No máximo {MAX_CONFIRM_ROWS} linhas por importação.")
        return value
