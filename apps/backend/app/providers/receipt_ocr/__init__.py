from functools import lru_cache

from app.config import settings
from app.providers.receipt_ocr.base import ReceiptOcrProvider
from app.providers.receipt_ocr.mock import MockReceiptOcrProvider


@lru_cache
def get_receipt_ocr_provider() -> ReceiptOcrProvider:
    if settings.receipt_ocr_provider == "mindee" and settings.mindee_api_key:
        from app.providers.receipt_ocr.mindee import MindeeProvider

        return MindeeProvider()

    return MockReceiptOcrProvider()
