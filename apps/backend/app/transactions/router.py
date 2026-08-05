from fastapi import APIRouter

from app.transactions import service
from app.transactions.schemas import TransactionCreate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(month: str | None = None, category_id: int | None = None):
    return await service.list_transactions(household_id=0, month=month, category_id=category_id)


@router.post("")
async def create_transaction(data: TransactionCreate):
    return await service.create_transaction(household_id=0, data=data)
