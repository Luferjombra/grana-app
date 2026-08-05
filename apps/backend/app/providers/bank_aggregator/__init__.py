from functools import lru_cache

from app.config import settings
from app.providers.bank_aggregator.base import BankAggregatorProvider
from app.providers.bank_aggregator.mock import MockBankAggregatorProvider


@lru_cache
def get_bank_aggregator_provider() -> BankAggregatorProvider:
    if settings.bank_aggregator_provider == "pluggy" and settings.pluggy_client_id:
        from app.providers.bank_aggregator.pluggy import PluggyProvider

        return PluggyProvider()

    return MockBankAggregatorProvider()
