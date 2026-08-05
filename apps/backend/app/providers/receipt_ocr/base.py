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
    async def extract(self, image_bytes: bytes) -> ExtractedReceipt: ...
