from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.budget import service
from app.budget.schemas import BudgetRuleUpdate

router = APIRouter(prefix="/dashboard", tags=["budget"])


@router.get("/summary")
async def dashboard_summary(month: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_dashboard_summary(current_user, month)


@router.get("/budget-rule")
async def get_budget_rule(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_budget_rule(current_user)


@router.patch("/budget-rule")
async def update_budget_rule(
    data: BudgetRuleUpdate, current_user: CurrentUser = Depends(get_current_user)
):
    return await service.update_budget_rule(current_user, data)
