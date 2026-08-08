from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.gamification import service

router = APIRouter(tags=["gamification"])


@router.get("/gamification/progress")
async def progress(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_progress(current_user)


@router.get("/gamification/achievements")
async def achievements(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_achievements(current_user)


@router.get("/roundup")
async def roundup_balance(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_roundup(current_user)


@router.post("/roundup/transfer")
async def roundup_transfer(current_user: CurrentUser = Depends(get_current_user)):
    """Registra que o usuário fez a transferência.

    Não move dinheiro: confirmação manual nesta fase. Transferência de verdade
    exigiria ITP via Open Finance, adiado na ADR 0001 — e um botão que promete
    mover dinheiro sem mover seria pior que não ter botão.
    """
    return await service.transfer_roundup(current_user)
