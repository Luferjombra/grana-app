from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.reserve import service
from app.reserve.schemas import ReserveUpdate

router = APIRouter(prefix="/emergency-reserve", tags=["emergency-reserve"])


@router.get("")
async def get_reserve(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_reserve(current_user)


@router.patch("")
async def update_reserve(
    data: ReserveUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.update_reserve(current_user, data)
