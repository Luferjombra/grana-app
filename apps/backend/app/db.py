from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_db() -> Client:
    """Client com a service role key — ignora RLS. Autorização por household/
    user já é resolvida em app/auth.py antes de qualquer query aqui."""
    return create_client(settings.supabase_url, settings.supabase_service_key)
