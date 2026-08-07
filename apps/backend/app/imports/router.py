from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.auth import CurrentUser, get_current_user
from app.imports import service
from app.imports.schemas import ImportConfirm
from app.notifications.engine import evaluate_after_transaction

router = APIRouter(prefix="/transactions/import", tags=["imports"])


@router.post("")
async def preview_import(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Só lê e devolve o preview — nada é gravado até a confirmação."""
    return await service.preview_import(current_user, file)


@router.post("/confirm")
async def confirm_import(
    data: ImportConfirm,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await service.confirm_import(current_user, data)

    # Um extrato costuma cobrir mais de um mês; reavalia cada um, senão o
    # alerta de teto ignoraria tudo que entrou de uma vez.
    for month in result["months_touched"]:
        background_tasks.add_task(
            evaluate_after_transaction, current_user.household_id, f"{month}-01"
        )

    return result
