from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.common import parse_month, today_local
from app.insights import service
from app.insights.service import DEFAULT_TOP_LIMIT

router = APIRouter(prefix="/insights", tags=["insights"])


def _month(month: str | None):
    """Mês corrente como default, igual ao dashboard: a tela abre no mês de
    hoje e não deveria ter que saber a data pra pedir isso."""
    return parse_month(month) if month else today_local().replace(day=1)


@router.get("/month-over-month")
async def month_over_month(
    month: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.month_over_month(current_user, _month(month))


@router.get("/recurring-subscriptions")
async def recurring_subscriptions(current_user: CurrentUser = Depends(get_current_user)):
    return await service.recurring_subscriptions(current_user)


@router.get("/top-transactions")
async def top_transactions(
    month: str | None = None,
    limit: int = DEFAULT_TOP_LIMIT,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.top_transactions(current_user, _month(month), limit)


@router.get("/three-month-average")
async def three_month_average(current_user: CurrentUser = Depends(get_current_user)):
    return await service.three_month_average(current_user)


@router.get("/health-score-breakdown")
async def health_score_breakdown(
    month: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.health_score_breakdown(current_user, _month(month))
