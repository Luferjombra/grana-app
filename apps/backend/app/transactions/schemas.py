from pydantic import BaseModel


class TransactionCreate(BaseModel):
    amount: str
    category_id: int
    type: str
    occurred_at: str
    merchant: str | None = None
    note: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None
