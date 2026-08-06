import asyncio
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException

from app.config import settings
from app.db import get_db


@dataclass
class CurrentUser:
    user_id: str
    household_id: int


async def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente.")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido.")

    # maybe_single().execute() retorna None (não um objeto com .data=None)
    # quando nenhuma linha casa — checar result antes de acessar .data.
    # Client do supabase-py é síncrono: roda em thread pra não bloquear o
    # event loop enquanto espera a resposta.
    query = get_db().table("profiles").select("household_id").eq("id", user_id).maybe_single()
    result = await asyncio.to_thread(query.execute)
    if result is None or not result.data:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")

    return CurrentUser(user_id=user_id, household_id=result.data["household_id"])
