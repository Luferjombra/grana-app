from app.providers.bank_aggregator.base import BankAggregatorProvider, ExternalTransaction


class MockBankAggregatorProvider(BankAggregatorProvider):
    """Ativo quando PLUGGY_CLIENT_ID/PLUGGY_CLIENT_SECRET não estão configurados."""

    async def create_connect_token(self, user_id: str) -> str:
        return f"mock-connect-token-{user_id}"

    async def sync_transactions(self, item_id: str, since: str) -> list[ExternalTransaction]:
        return [
            ExternalTransaction(
                external_id="mock-tx-1",
                amount=42.50,
                occurred_at=since,
                merchant="Mercado Mock",
                installment_number=None,
                installment_total=None,
                raw_payload={"mock": True},
            )
        ]

    async def get_connection_status(self, item_id: str) -> str:
        return "active"
