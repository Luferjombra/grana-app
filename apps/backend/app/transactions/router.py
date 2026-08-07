from fastapi import APIRouter, Depends, Response

from app.auth import CurrentUser, get_current_user
from app.transactions import service
from app.transactions.schemas import TransactionCreate, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(
    month: str | None = None,
    category_id: int | None = None,
    type: str | None = None,
    cursor: str | None = None,
    limit: int = service.DEFAULT_PAGE_SIZE,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.list_transactions(
        current_user, month=month, category_id=category_id, type=type, cursor=cursor, limit=limit
    )


@router.get("/{transaction_id}")
async def get_transaction(
    transaction_id: int, current_user: CurrentUser = Depends(get_current_user)
):
    return await service.get_transaction(current_user, transaction_id)


@router.post("", status_code=201)
async def create_transaction(
    data: TransactionCreate, current_user: CurrentUser = Depends(get_current_user)
):
    return await service.create_transaction(current_user, data)


@router.patch("/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.update_transaction(current_user, transaction_id, data)


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int, current_user: CurrentUser = Depends(get_current_user)
):
    await service.delete_transaction(current_user, transaction_id)
    return Response(status_code=204)
