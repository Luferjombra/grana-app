from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.auth import CurrentUser, get_current_user
from app.notifications.engine import evaluate_after_transaction
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


# O motor de alertas roda em background (specs/07: "após commit da
# transaction") pra não somar latência ao registro de gasto, que é a ação
# mais frequente do app. O app enxerga o alerta no próximo GET /notifications.
@router.post("", status_code=201)
async def create_transaction(
    data: TransactionCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    transaction = await service.create_transaction(current_user, data)
    background_tasks.add_task(
        evaluate_after_transaction, current_user.household_id, transaction["occurred_at"]
    )
    return transaction


@router.patch("/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    transaction = await service.update_transaction(current_user, transaction_id, data)
    background_tasks.add_task(
        evaluate_after_transaction, current_user.household_id, transaction["occurred_at"]
    )
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    removed = await service.delete_transaction(current_user, transaction_id)
    # Apagar também muda os totais: sem reavaliar, um alerta de teto ficaria
    # de pé depois que o gasto que o causou deixou de existir.
    background_tasks.add_task(
        evaluate_after_transaction, current_user.household_id, removed["occurred_at"]
    )
    return Response(status_code=204)
