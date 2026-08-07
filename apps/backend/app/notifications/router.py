from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.notifications import service
from app.notifications.schemas import PushTokenRegister

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(
    unread: bool | None = None,
    limit: int = service.DEFAULT_LIMIT,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await service.list_notifications(current_user, unread=unread, limit=limit)


@router.patch("/notifications/{notification_id}/read")
async def mark_read(notification_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return await service.mark_read(current_user, notification_id)


@router.post("/push-tokens")
async def register_push_token(
    data: PushTokenRegister, current_user: CurrentUser = Depends(get_current_user)
):
    return await service.register_push_token(current_user, data)
