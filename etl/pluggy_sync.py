"""Cron diário: sincroniza transações de todas as contas Pluggy ativas.

Ver specs/06-adaptador-open-finance-pluggy.md — reaproveita
`BankAggregatorProvider.sync_transactions`, pega transações novas desde
`accounts.last_synced_at`.
"""

from etl.common.etl_run import track_run


def main() -> None:
    with track_run("pluggy_sync"):
        raise NotImplementedError


if __name__ == "__main__":
    main()
