"""Cron diário (meia-noite local): reavalia os alertas de todo household com
transação no mês, mesmo sem evento novo — cobre a mudança de dias corridos,
que muda a projeção sozinha.

Ver specs/07. Importa `app.notifications.engine` do backend de propósito: a
spec exige a mesma regra nos dois gatilhos, sem duplicar. Por isso o job
precisa do pacote `grana-backend` instalado junto (ver README).
"""

import asyncio
from datetime import date

from app.common import month_bounds, previous_month, today_local
from app.db import get_db
from app.notifications.engine import evaluate_daily

from etl.common.etl_run import track_run


def households_with_activity(month_start: date) -> set[int]:
    """PostgREST não expõe DISTINCT — dedupe no cliente. Aceitável na escala
    de um app pessoal; se crescer, virar uma RPC no Postgres."""
    start, end = month_bounds(month_start)
    result = (
        get_db()
        .table("transactions")
        .select("household_id")
        .gte("occurred_at", start.isoformat())
        .lt("occurred_at", end.isoformat())
        .execute()
    )
    return {row["household_id"] for row in (result.data or [])}


async def run() -> int:
    today = today_local()
    current_month = today.replace(day=1)

    households = households_with_activity(current_month)
    if today.day == 1:
        # No dia 1 o mês anterior também é fechado (goal_hit), e ele pode ter
        # households que não têm nada lançado ainda no mês novo.
        households |= households_with_activity(previous_month(current_month))

    for household_id in households:
        await evaluate_daily(household_id, today=today)

    return len(households)


def main() -> None:
    with track_run("projection_recompute") as run_info:
        run_info["rows_upserted"] = asyncio.run(run())


if __name__ == "__main__":
    main()
