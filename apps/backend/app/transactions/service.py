from app.transactions.schemas import TransactionCreate


async def list_transactions(household_id: int, month: str | None, category_id: int | None):
    raise NotImplementedError


async def create_transaction(household_id: int, data: TransactionCreate):
    raise NotImplementedError
