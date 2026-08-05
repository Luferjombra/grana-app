from pydantic import BaseModel


class PushTokenRegister(BaseModel):
    token: str
    platform: str
