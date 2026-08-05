from fastapi import APIRouter

from app.gamification import service

router = APIRouter(tags=["gamification"])


@router.get("/gamification/progress")
async def progress():
    return await service.get_progress(user_id="")


@router.get("/gamification/achievements")
async def achievements():
    return await service.get_achievements(user_id="")


@router.get("/roundup")
async def roundup_balance():
    return await service.get_roundup_balance(user_id="")
