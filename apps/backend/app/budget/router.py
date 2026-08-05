from fastapi import APIRouter

from app.budget import service
from app.budget.schemas import BudgetRuleUpdate

router = APIRouter(prefix="/dashboard", tags=["budget"])


@router.get("/summary")
async def dashboard_summary(month: str):
    return await service.get_dashboard_summary(household_id=0, month=month)


@router.get("/budget-rule")
async def get_budget_rule():
    return await service.get_budget_rule(household_id=0)


@router.patch("/budget-rule")
async def update_budget_rule(data: BudgetRuleUpdate):
    return await service.update_budget_rule(household_id=0, data=data)
