from pydantic import BaseModel


class ReceiptConfirm(BaseModel):
    """Campos extraídos pelo OCR, confirmados (ou editados) pelo usuário
    antes de virarem uma transaction de verdade — specs/05."""

    amount: str
    category_id: int
    occurred_at: str
    merchant: str | None = None
    note: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None
