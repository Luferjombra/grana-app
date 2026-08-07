import asyncio

from fastapi import HTTPException

from app.auth import CurrentUser
from app.db import get_db
from app.notifications.schemas import PushTokenRegister

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

NOTIFICATION_COLUMNS = (
    "id, type, severity, title, message, read, reference_month, subject, created_at"
)


async def list_notifications(
    current_user: CurrentUser, unread: bool | None = None, limit: int = DEFAULT_LIMIT
) -> dict:
    limit = max(1, min(limit, MAX_LIMIT))

    query = (
        get_db()
        .table("notifications")
        .select(NOTIFICATION_COLUMNS)
        .eq("user_id", current_user.user_id)
    )
    if unread:
        query = query.eq("read", False)

    query = query.order("created_at", desc=True).order("id", desc=True).limit(limit)
    result = await asyncio.to_thread(query.execute)

    return {
        "items": result.data or [],
        "unread_count": await count_unread(current_user),
    }


async def count_unread(current_user: CurrentUser) -> int:
    """Contagem própria, não derivada da página: contar sobre `items` daria o
    número errado assim que houvesse mais alertas que o limite, e o badge do
    sino mostraria um valor menor que o real."""
    query = (
        get_db()
        .table("notifications")
        .select("id", count="exact", head=True)
        .eq("user_id", current_user.user_id)
        .eq("read", False)
    )
    result = await asyncio.to_thread(query.execute)
    return result.count or 0


async def mark_read(current_user: CurrentUser, notification_id: int) -> dict:
    """Marcar como lido libera a chave de idempotência do motor (o índice
    único é parcial em read = false), então um alerta novo do mesmo tipo pode
    voltar a ser criado se a situação persistir — comportamento pedido na
    spec 07."""
    query = (
        get_db()
        .table("notifications")
        .update({"read": True})
        .eq("id", notification_id)
        .eq("user_id", current_user.user_id)
    )
    result = await asyncio.to_thread(query.execute)
    if not result.data:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    return result.data[0]


async def register_push_token(current_user: CurrentUser, data: PushTokenRegister):
    # TODO(spec 08): precisa de uma tabela `push_tokens`, que ainda não existe
    # no schema — entra junto com o projeto Expo/EAS.
    raise NotImplementedError
