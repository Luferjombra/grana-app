from fastapi import APIRouter

from app.notifications import service
from app.notifications.schemas import PushTokenRegister

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(unread: bool | None = None):
    return await service.list_notifications(user_id="", unread=unread)


@router.patch("/notifications/{notification_id}/read")
async def mark_read(notification_id: int):
    return await service.mark_read(user_id="", notification_id=notification_id)


@router.post("/push-tokens")
async def register_push_token(data: PushTokenRegister):
    return await service.register_push_token(user_id="", data=data)
