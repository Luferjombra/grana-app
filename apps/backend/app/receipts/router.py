from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.auth import CurrentUser, get_current_user
from app.receipts import service
from app.receipts.schemas import ReceiptConfirm

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("")
async def create_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.create_receipt(current_user, file, background_tasks)


@router.get("/{receipt_id}")
async def get_receipt(receipt_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_receipt(current_user, receipt_id)


@router.post("/{receipt_id}/confirm")
async def confirm_receipt(
    receipt_id: int,
    data: ReceiptConfirm,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.confirm_receipt(current_user, receipt_id, data)
