from app.budget.schemas import BudgetRuleUpdate


async def get_dashboard_summary(household_id: int, month: str):
    raise NotImplementedError


async def get_budget_rule(household_id: int):
    raise NotImplementedError


async def update_budget_rule(household_id: int, data: BudgetRuleUpdate):
    raise NotImplementedError
