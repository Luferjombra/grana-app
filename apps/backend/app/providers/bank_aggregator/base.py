from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExternalTransaction:
    external_id: str
    amount: float
    occurred_at: str
    merchant: str | None
    installment_number: int | None
    installment_total: int | None
    raw_payload: dict


class BankAggregatorProvider(ABC):
    @abstractmethod
    async def create_connect_token(self, user_id: str) -> str:
        """Token de uso único pro widget de conexão do banco no app."""

    @abstractmethod
    async def sync_transactions(self, item_id: str, since: str) -> list[ExternalTransaction]: ...

    @abstractmethod
    async def get_connection_status(self, item_id: str) -> str:
        """'active' | 'error' | 'disconnected'"""
