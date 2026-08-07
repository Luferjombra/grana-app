from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.profile import service
from app.profile.schemas import IncomeCreate, OnboardingPayload

router = APIRouter(tags=["profile"])


@router.get("/profile")
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_profile(current_user)


@router.post("/onboarding")
async def complete_onboarding(
    data: OnboardingPayload, current_user: CurrentUser = Depends(get_current_user)
):
    return await service.complete_onboarding(current_user, data)


@router.get("/incomes")
async def list_incomes(current_user: CurrentUser = Depends(get_current_user)):
    return await service.list_incomes(current_user)


@router.post("/incomes", status_code=201)
async def create_income(data: IncomeCreate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.create_income(current_user, data)
