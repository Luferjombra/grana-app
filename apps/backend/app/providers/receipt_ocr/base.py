from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExtractedReceipt:
    merchant: str | None
    amount: float | None
    occurred_at: str | None  # ISO date
    category_hint: str | None
    raw_payload: dict


class ReceiptOcrProvider(ABC):
    @abstractmethod
    async def extract(self, image_bytes: bytes, filename: str) -> ExtractedReceipt:
        """filename precisa preservar a extensão original (ex: 'foto.jpg') —
        alguns providers (Mindee) inferem o mimetype a partir dela."""
        ...


class ReceiptOcrInvalidApiKeyError(Exception):
    """Chave de API do provider de OCR inválida ou não configurada (401)."""


class ReceiptOcrQuotaExceededError(Exception):
    """Limite de créditos/cota do provider de OCR excedido (402/429)."""
