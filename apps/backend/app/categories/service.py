import asyncio

from app.auth import CurrentUser
from app.common import BUCKETS
from app.db import get_db

BUCKET_ORDER = {bucket: index for index, bucket in enumerate(BUCKETS)}


async def list_categories(current_user: CurrentUser) -> list[dict]:
    """Categorias padrão do sistema (household_id null) mais as próprias.

    O backend usa a service role, que ignora RLS — então o escopo por
    household é aplicado aqui na mão, espelhando a policy de `categories`.
    """
    query = (
        get_db()
        .table("categories")
        .select("id, name, bucket, icon, is_default, household_id")
        .or_(f"household_id.is.null,household_id.eq.{current_user.household_id}")
    )
    result = await asyncio.to_thread(query.execute)

    # Agrupadas por bucket na ordem 50-30-20, que é como o app apresenta —
    # deixar o cliente reordenar convidaria cada tela a fazer diferente.
    return sorted(
        (
            {key: value for key, value in row.items() if key != "household_id"}
            for row in (result.data or [])
        ),
        key=lambda row: (BUCKET_ORDER.get(row["bucket"], len(BUCKETS)), row["name"]),
    )
