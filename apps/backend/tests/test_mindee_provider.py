from dataclasses import dataclass

import pytest
from mindee.error import MindeeHTTPClientError

from app.providers.receipt_ocr.base import (
    ReceiptOcrInvalidApiKeyError,
    ReceiptOcrQuotaExceededError,
)
from app.providers.receipt_ocr.mindee import MindeeProvider


@dataclass
class FakeField:
    value: object
    confidence: float = 1.0


@dataclass
class FakePrediction:
    supplier_name: FakeField
    total_amount: FakeField
    date: FakeField
    category: FakeField


@dataclass
class FakeInference:
    prediction: FakePrediction


@dataclass
class FakeDocument:
    inference: FakeInference


@dataclass
class FakeResult:
    document: FakeDocument
    raw_http: str = "{}"


def make_provider(monkeypatch) -> MindeeProvider:
    monkeypatch.setattr("app.providers.receipt_ocr.mindee.settings.mindee_api_key", "fake-key")
    return MindeeProvider()


async def test_extract_maps_confident_fields(monkeypatch):
    provider = make_provider(monkeypatch)
    fake_result = FakeResult(
        document=FakeDocument(
            inference=FakeInference(
                prediction=FakePrediction(
                    supplier_name=FakeField("Mercado Central", 0.95),
                    total_amount=FakeField(42.5, 0.9),
                    date=FakeField("2026-08-05", 0.8),
                    category=FakeField("food", 0.7),
                )
            )
        ),
        raw_http='{"mocked": true}',
    )
    monkeypatch.setattr(provider._client, "parse", lambda *a, **k: fake_result)

    receipt = await provider.extract(b"fake-image-bytes", "receipt.jpg")

    assert receipt.merchant == "Mercado Central"
    assert receipt.amount == 42.5
    assert receipt.occurred_at == "2026-08-05"
    assert receipt.category_hint == "food"
    assert receipt.raw_payload == {"mocked": True}


async def test_extract_nulls_low_confidence_fields(monkeypatch):
    provider = make_provider(monkeypatch)
    fake_result = FakeResult(
        document=FakeDocument(
            inference=FakeInference(
                prediction=FakePrediction(
                    supplier_name=FakeField("Talvez Mercado", 0.2),
                    total_amount=FakeField(None, 0.0),
                    date=FakeField("2026-08-05", 0.9),
                    category=FakeField("food", 0.9),
                )
            )
        ),
    )
    monkeypatch.setattr(provider._client, "parse", lambda *a, **k: fake_result)

    receipt = await provider.extract(b"fake-image-bytes", "receipt.jpg")

    assert receipt.merchant is None  # baixa confiança
    assert receipt.amount is None  # sem valor extraído


async def test_extract_maps_401_to_invalid_api_key_error(monkeypatch):
    provider = make_provider(monkeypatch)

    def raise_401(*_args, **_kwargs):
        raise MindeeHTTPClientError({"code": "401", "message": "bad key"}, "url", 401)

    monkeypatch.setattr(provider._client, "parse", raise_401)

    with pytest.raises(ReceiptOcrInvalidApiKeyError):
        await provider.extract(b"fake-image-bytes", "receipt.jpg")


@pytest.mark.parametrize("status_code", [402, 429])
async def test_extract_maps_quota_errors(monkeypatch, status_code):
    provider = make_provider(monkeypatch)

    def raise_quota(*_args, **_kwargs):
        raise MindeeHTTPClientError(
            {"code": str(status_code), "message": "quota"}, "url", status_code
        )

    monkeypatch.setattr(provider._client, "parse", raise_quota)

    with pytest.raises(ReceiptOcrQuotaExceededError):
        await provider.extract(b"fake-image-bytes", "receipt.jpg")
