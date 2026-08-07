import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.auth import CurrentUser
from app.db import get_db
from app.providers.receipt_ocr import get_receipt_ocr_provider
from app.receipts.schemas import ReceiptConfirm

BUCKET = "receipts"
ACCEPTED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Verificação de assinatura pra tipos onde é simples (jpeg/png). heic/heif
# exigem parsear a ftyp box do container — não vale o esforço agora, então
# esses dois só validam pelo Content-Type mesmo (ver _looks_like_content_type).
MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def _looks_like_content_type(content_type: str, data: bytes) -> bool:
    signatures = MAGIC_BYTES.get(content_type)
    if signatures is None:
        return True
    return any(data.startswith(sig) for sig in signatures)


async def create_receipt(
    current_user: CurrentUser, file: UploadFile, background_tasks: BackgroundTasks
) -> dict:
    if file.content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Formato de imagem não suportado.")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que o limite de 10MB.")
    if not _looks_like_content_type(file.content_type, image_bytes):
        raise HTTPException(status_code=400, detail="O arquivo não parece ser uma imagem válida.")

    filename = file.filename or "receipt.jpg"
    extension = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
    storage_path = f"{current_user.user_id}/{uuid.uuid4()}.{extension}"

    db = get_db()

    # Cria a linha antes de subir o arquivo: se o upload falhar, só sobra uma
    # linha órfã (fácil de apagar abaixo) em vez de um objeto órfão no Storage
    # (sem job de limpeza pra isso).
    insert_query = db.table("receipts").insert(
        {"user_id": current_user.user_id, "image_url": storage_path, "status": "pending"}
    )
    result = await asyncio.to_thread(insert_query.execute)
    receipt = result.data[0]

    try:
        await asyncio.to_thread(
            db.storage.from_(BUCKET).upload,
            storage_path,
            image_bytes,
            file_options={"content-type": file.content_type},
        )
    except Exception as exc:
        delete_query = db.table("receipts").delete().eq("id", receipt["id"])
        await asyncio.to_thread(delete_query.execute)
        raise HTTPException(
            status_code=502, detail="Falha ao enviar a imagem. Tente de novo."
        ) from exc

    background_tasks.add_task(_process_receipt, receipt["id"], image_bytes, filename)

    return receipt


async def _process_receipt(receipt_id: int, image_bytes: bytes, filename: str) -> None:
    db = get_db()
    provider = get_receipt_ocr_provider()

    try:
        extracted = await provider.extract(image_bytes, filename)
    except Exception:
        # Cobre erros conhecidos do provider (chave inválida, cota excedida —
        # specs/05) e qualquer falha inesperada: sem isso, uma exceção aqui
        # deixaria o recibo em 'pending' pra sempre, já que roda em background.
        update_query = (
            db.table("receipts")
            .update({"status": "failed", "processed_at": datetime.now(UTC).isoformat()})
            .eq("id", receipt_id)
        )
        await asyncio.to_thread(update_query.execute)
        return

    update_query = (
        db.table("receipts")
        .update(
            {
                "status": "processed",
                "extracted_payload": {
                    "merchant": extracted.merchant,
                    "amount": extracted.amount,
                    "occurred_at": extracted.occurred_at,
                    "category_hint": extracted.category_hint,
                    "raw": extracted.raw_payload,
                },
                "processed_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", receipt_id)
    )
    await asyncio.to_thread(update_query.execute)


async def get_receipt(current_user: CurrentUser, receipt_id: int) -> dict:
    query = (
        get_db()
        .table("receipts")
        .select("*")
        .eq("id", receipt_id)
        .eq("user_id", current_user.user_id)
        .maybe_single()
    )
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        raise HTTPException(status_code=404, detail="Recibo não encontrado.")
    return result.data


async def confirm_receipt(current_user: CurrentUser, receipt_id: int, data: ReceiptConfirm) -> dict:
    db = get_db()

    receipt_query = (
        db.table("receipts")
        .select("*")
        .eq("id", receipt_id)
        .eq("user_id", current_user.user_id)
        .maybe_single()
    )
    receipt_result = await asyncio.to_thread(receipt_query.execute)
    if receipt_result is None or not receipt_result.data:
        raise HTTPException(status_code=404, detail="Recibo não encontrado.")

    if receipt_result.data["matched_transaction_id"]:
        raise HTTPException(status_code=409, detail="Este recibo já foi confirmado.")

    insert_query = db.table("transactions").insert(
        {
            "user_id": current_user.user_id,
            "household_id": current_user.household_id,
            "category_id": data.category_id,
            "type": "expense",
            "amount": data.amount,
            "occurred_at": data.occurred_at,
            "merchant": data.merchant,
            "note": data.note,
            "entry_method": "receipt_ocr",
            "receipt_id": receipt_id,
            # Recibo não parcela hoje — ver a nota em ReceiptConfirm.
            "installment_number": None,
            "installment_total": None,
        }
    )
    transaction_result = await asyncio.to_thread(insert_query.execute)
    transaction = transaction_result.data[0]

    # Reivindica o recibo atomicamente (só se ainda não tiver sido
    # confirmado) — é essa condição, não a checagem lá em cima, que decide
    # a corrida entre duas confirmações concorrentes do mesmo recibo.
    claim_query = (
        db.table("receipts")
        .update({"matched_transaction_id": transaction["id"]})
        .eq("id", receipt_id)
        .eq("user_id", current_user.user_id)
        .is_("matched_transaction_id", "null")
    )
    claim_result = await asyncio.to_thread(claim_query.execute)

    if not claim_result.data:
        # Perdeu a corrida pra outra confirmação concorrente — desfaz a
        # transaction criada nesta chamada pra não duplicar o gasto.
        delete_query = db.table("transactions").delete().eq("id", transaction["id"])
        await asyncio.to_thread(delete_query.execute)
        raise HTTPException(status_code=409, detail="Este recibo já foi confirmado.")

    return transaction
