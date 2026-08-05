import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from supabase import Client, create_client


def get_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


@contextmanager
def track_run(job: str) -> Iterator[dict]:
    """Registra a execução do job em `etl_runs`, mesma convenção da plataforma de investimentos.

    Uso:
        with track_run("pluggy_sync") as run:
            run["rows_upserted"] = sync()
    """
    client = get_client()
    run = {"rows_upserted": 0}

    row = (
        client.table("etl_runs")
        .insert({"job": job, "started_at": datetime.now(UTC).isoformat(), "status": "running"})
        .execute()
    )
    run_id = row.data[0]["id"]

    try:
        yield run
    except Exception as exc:
        client.table("etl_runs").update(
            {
                "finished_at": datetime.now(UTC).isoformat(),
                "status": "error",
                "error_msg": str(exc),
            }
        ).eq("id", run_id).execute()
        raise
    else:
        client.table("etl_runs").update(
            {
                "finished_at": datetime.now(UTC).isoformat(),
                "status": "success",
                "rows_upserted": run.get("rows_upserted", 0),
            }
        ).eq("id", run_id).execute()
