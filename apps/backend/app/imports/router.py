from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from app.auth import CurrentUser, get_current_user
from app.common import today_local
from app.imports import service
from app.imports.schemas import ImportConfirm
from app.notifications.engine import evaluate_after_transaction

router = APIRouter(prefix="/transactions/import", tags=["imports"])


@router.post("")
async def preview_import(
    file: UploadFile = File(...),
    month: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Só lê e devolve o preview — nada é gravado até a confirmação.

    `month` (AAAA-MM) escolhe qual mês do arquivo revisar. Omitido, vem o mais
    recente: extrato de 12 meses cobraria 169 decisões de uma vez, e resolver um
    mês já ensina as regras que resolvem os outros (specs/11).
    """
    return await service.preview_import(current_user, file, month)


@router.post("/confirm")
async def confirm_import(
    data: ImportConfirm,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await service.confirm_import(current_user, data)

    # Só o mês corrente gera alerta. Extrato de histórico cobre meses já
    # encerrados, e avaliá-los criaria hoje alertas de teto e de "projeção
    # negativa" sobre orçamentos de anos atrás — num extrato real de 12 meses
    # isso viravam dezenas de notificações inúteis e enganosas, já que num mês
    # fechado a "projeção" é só o gasto que de fato aconteceu.
    # Os meses passados seguem corretos no dashboard e nos insights: os tetos
    # deles são gerados sob demanda quando o mês é consultado.
    current_month = today_local().strftime("%Y-%m")
    if current_month in result["months_touched"]:
        background_tasks.add_task(
            evaluate_after_transaction, current_user.household_id, f"{current_month}-01"
        )

    return result
