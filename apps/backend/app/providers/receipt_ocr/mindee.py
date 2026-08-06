import asyncio
import json

from mindee import product
from mindee.error import MindeeHTTPError
from mindee.input import BytesInput
from mindee.v1 import Client

from app.config import settings
from app.providers.receipt_ocr.base import (
    ExtractedReceipt,
    ReceiptOcrInvalidApiKeyError,
    ReceiptOcrProvider,
    ReceiptOcrQuotaExceededError,
)

# Abaixo disso, tratamos o campo como não confiável o bastante pra preencher
# sozinho — mesmo efeito de vir null da API (spec 05: pedir confirmação
# manual em vez de aceitar um valor de baixa confiança sem o usuário ver).
LOW_CONFIDENCE_THRESHOLD = 0.5


class MindeeProvider(ReceiptOcrProvider):
    def __init__(self) -> None:
        self._client = Client(api_key=settings.mindee_api_key)

    async def extract(self, image_bytes: bytes, filename: str) -> ExtractedReceipt:
        input_source = BytesInput(raw_bytes=image_bytes, filename=filename)

        try:
            # client.parse é síncrono (httpx.Client) — roda em thread pra não
            # bloquear o event loop enquanto espera a resposta do Mindee.
            result = await asyncio.to_thread(self._client.parse, product.ReceiptV5, input_source)
        except MindeeHTTPError as exc:
            if exc.status_code == 401:
                raise ReceiptOcrInvalidApiKeyError(str(exc)) from exc
            if exc.status_code in (402, 429):
                raise ReceiptOcrQuotaExceededError(str(exc)) from exc
            raise

        prediction = result.document.inference.prediction

        return ExtractedReceipt(
            merchant=_confident_value(prediction.supplier_name),
            amount=_confident_value(prediction.total_amount),
            occurred_at=_confident_value(prediction.date),
            category_hint=_confident_value(prediction.category),
            raw_payload=json.loads(result.raw_http),
        )


def _confident_value(field):
    if field.value is None or field.confidence < LOW_CONFIDENCE_THRESHOLD:
        return None
    return field.value
