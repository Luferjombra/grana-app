from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.categories import service

router = APIRouter(tags=["categories"])


@router.get("/categories")
async def list_categories(current_user: CurrentUser = Depends(get_current_user)):
    return await service.list_categories(current_user)
