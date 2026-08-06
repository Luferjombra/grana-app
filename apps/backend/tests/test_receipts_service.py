from dataclasses import dataclass

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from starlette.datastructures import Headers

from app.auth import CurrentUser
from app.receipts import service
from app.receipts.schemas import ReceiptConfirm


@dataclass
class FakeResult:
    data: object


class FakeQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self._op = None
        self._payload = None
        self._filters = {}
        self._is_null_filters = []

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def select(self, *_args, **_kwargs):
        self._op = self._op or "select"
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def is_(self, key, value):
        assert value == "null", "fake só suporta is_(key, 'null')"
        self._is_null_filters.append(key)
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return self.db.execute(
            self.table_name, self._op, self._payload, self._filters, self._is_null_filters
        )


class FakeStorage:
    def __init__(self):
        self.uploaded = []
        self._bucket = None

    def from_(self, bucket):
        self._bucket = bucket
        return self

    def upload(self, path, data, file_options=None):
        self.uploaded.append({"bucket": self._bucket, "path": path, "file_options": file_options})
        return {"path": path}


class FakeDb:
    def __init__(self):
        self.storage = FakeStorage()
        self.receipts: dict[int, dict] = {}
        self.transactions: dict[int, dict] = {}
        self._next_receipt_id = 1
        self._next_transaction_id = 1

    def table(self, name):
        return FakeQuery(self, name)

    def execute(self, table_name, op, payload, filters, is_null_filters=()):
        store = self.receipts if table_name == "receipts" else self.transactions

        if op == "insert":
            is_receipts = table_name == "receipts"
            next_id = self._next_receipt_id if is_receipts else self._next_transaction_id
            row = {"id": next_id, **payload}
            if table_name == "receipts":
                row.setdefault("matched_transaction_id", None)
                self._next_receipt_id += 1
            else:
                self._next_transaction_id += 1
            store[next_id] = row
            return FakeResult(data=[row])

        if op == "update":
            matches = [row for row in store.values() if _matches(row, filters, is_null_filters)]
            for row in matches:
                row.update(payload)
            return FakeResult(data=matches)

        if op == "delete":
            matches = [row for row in store.values() if _matches(row, filters, is_null_filters)]
            for row in matches:
                del store[row["id"]]
            return FakeResult(data=matches)

        if op == "select":
            matches = [row for row in store.values() if _matches(row, filters, is_null_filters)]
            return FakeResult(data=matches[0]) if matches else None

        raise AssertionError(f"unexpected op {op}")


def _matches(row: dict, filters: dict, is_null_filters=()) -> bool:
    if not all(row.get(key) == value for key, value in filters.items()):
        return False
    return all(row.get(key) is None for key in is_null_filters)


def make_upload_file(content: bytes, content_type: str, filename: str) -> UploadFile:
    headers = Headers({"content-type": content_type})
    return UploadFile(filename=filename, file=__import__("io").BytesIO(content), headers=headers)


CURRENT_USER = CurrentUser(user_id="user-1", household_id=42)


async def test_create_receipt_rejects_unsupported_content_type(monkeypatch):
    monkeypatch.setattr(service, "get_db", lambda: FakeDb())
    file = make_upload_file(b"not-an-image", "application/pdf", "receipt.pdf")

    with pytest.raises(HTTPException) as exc_info:
        await service.create_receipt(CURRENT_USER, file, BackgroundTasks())
    assert exc_info.value.status_code == 400


async def test_create_receipt_rejects_spoofed_content_type(monkeypatch):
    monkeypatch.setattr(service, "get_db", lambda: FakeDb())
    file = make_upload_file(b"this is actually just text", "image/jpeg", "receipt.jpg")

    with pytest.raises(HTTPException) as exc_info:
        await service.create_receipt(CURRENT_USER, file, BackgroundTasks())
    assert exc_info.value.status_code == 400


async def test_create_receipt_rejects_oversized_image(monkeypatch):
    monkeypatch.setattr(service, "get_db", lambda: FakeDb())
    monkeypatch.setattr(service, "MAX_UPLOAD_BYTES", 10)
    file = make_upload_file(b"x" * 100, "image/jpeg", "receipt.jpg")

    with pytest.raises(HTTPException) as exc_info:
        await service.create_receipt(CURRENT_USER, file, BackgroundTasks())
    assert exc_info.value.status_code == 400


async def test_create_receipt_uploads_and_inserts_pending_row(monkeypatch):
    fake_db = FakeDb()
    monkeypatch.setattr(service, "get_db", lambda: fake_db)
    file = make_upload_file(b"\xff\xd8\xff" + b"fake-jpeg-bytes", "image/jpeg", "receipt.jpg")

    receipt = await service.create_receipt(CURRENT_USER, file, BackgroundTasks())

    assert receipt["status"] == "pending"
    assert receipt["user_id"] == "user-1"
    assert len(fake_db.storage.uploaded) == 1
    assert fake_db.storage.uploaded[0]["bucket"] == "receipts"
    assert fake_db.storage.uploaded[0]["path"].startswith("user-1/")


async def test_get_receipt_not_found_for_other_user(monkeypatch):
    fake_db = FakeDb()
    fake_db.receipts[1] = {"id": 1, "user_id": "someone-else", "status": "pending"}
    monkeypatch.setattr(service, "get_db", lambda: fake_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_receipt(CURRENT_USER, 1)
    assert exc_info.value.status_code == 404


async def test_get_receipt_returns_own_receipt(monkeypatch):
    fake_db = FakeDb()
    fake_db.receipts[1] = {"id": 1, "user_id": "user-1", "status": "processed"}
    monkeypatch.setattr(service, "get_db", lambda: fake_db)

    receipt = await service.get_receipt(CURRENT_USER, 1)
    assert receipt["status"] == "processed"


async def test_confirm_receipt_creates_transaction_and_links_receipt(monkeypatch):
    fake_db = FakeDb()
    fake_db.receipts[1] = {
        "id": 1,
        "user_id": "user-1",
        "status": "processed",
        "matched_transaction_id": None,
    }
    monkeypatch.setattr(service, "get_db", lambda: fake_db)

    data = ReceiptConfirm(
        amount="42.50", category_id=3, occurred_at="2026-08-05", merchant="Mercado"
    )
    transaction = await service.confirm_receipt(CURRENT_USER, 1, data)

    assert transaction["entry_method"] == "receipt_ocr"
    assert transaction["receipt_id"] == 1
    assert transaction["household_id"] == 42
    assert fake_db.receipts[1]["matched_transaction_id"] == transaction["id"]


async def test_confirm_receipt_rejects_already_confirmed(monkeypatch):
    fake_db = FakeDb()
    fake_db.receipts[1] = {
        "id": 1,
        "user_id": "user-1",
        "status": "processed",
        "matched_transaction_id": 99,
    }
    monkeypatch.setattr(service, "get_db", lambda: fake_db)

    data = ReceiptConfirm(amount="42.50", category_id=3, occurred_at="2026-08-05")
    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_receipt(CURRENT_USER, 1, data)
    assert exc_info.value.status_code == 409


async def test_process_receipt_marks_failed_on_provider_error(monkeypatch):
    fake_db = FakeDb()
    fake_db.receipts[1] = {"id": 1, "user_id": "user-1", "status": "pending"}
    monkeypatch.setattr(service, "get_db", lambda: fake_db)

    class FailingProvider:
        async def extract(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(service, "get_receipt_ocr_provider", lambda: FailingProvider())

    await service._process_receipt(1, b"bytes", "receipt.jpg")

    assert fake_db.receipts[1]["status"] == "failed"


async def test_process_receipt_marks_processed_on_success(monkeypatch):
    fake_db = FakeDb()
    fake_db.receipts[1] = {"id": 1, "user_id": "user-1", "status": "pending"}
    monkeypatch.setattr(service, "get_db", lambda: fake_db)

    @dataclass
    class FakeExtracted:
        merchant: str | None
        amount: float | None
        occurred_at: str | None
        category_hint: str | None
        raw_payload: dict

    class WorkingProvider:
        async def extract(self, *_args, **_kwargs):
            return FakeExtracted("Mercado", 10.0, "2026-08-05", "food", {"raw": True})

    monkeypatch.setattr(service, "get_receipt_ocr_provider", lambda: WorkingProvider())

    await service._process_receipt(1, b"bytes", "receipt.jpg")

    assert fake_db.receipts[1]["status"] == "processed"
    assert fake_db.receipts[1]["extracted_payload"]["merchant"] == "Mercado"
