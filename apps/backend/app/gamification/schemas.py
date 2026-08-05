from pydantic import BaseModel


class RoundupTransfer(BaseModel):
    amount: str
