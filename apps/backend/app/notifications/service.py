from app.notifications.schemas import PushTokenRegister


async def list_notifications(user_id: str, unread: bool | None):
    raise NotImplementedError


async def mark_read(user_id: str, notification_id: int):
    raise NotImplementedError


async def register_push_token(user_id: str, data: PushTokenRegister):
    raise NotImplementedError
