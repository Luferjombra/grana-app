import hashlib

from app.providers.receipt_ocr.base import ExtractedReceipt, ReceiptOcrProvider


class MockReceiptOcrProvider(ReceiptOcrProvider):
    """Determinístico (hash da imagem) — usado quando MINDEE_API_KEY não está configurada."""

    async def extract(self, image_bytes: bytes) -> ExtractedReceipt:
        digest = hashlib.sha256(image_bytes).hexdigest()
        fake_amount = int(digest[:4], 16) / 100

        return ExtractedReceipt(
            merchant="Mercado Mock",
            amount=fake_amount,
            occurred_at=None,
            category_hint=None,
            raw_payload={"mock": True, "hash": digest},
        )
