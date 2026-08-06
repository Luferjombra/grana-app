from dataclasses import dataclass

import jwt
import pytest
from fastapi import HTTPException

from app import auth


@dataclass
class FakeResult:
    data: dict | None


class FakeQuery:
    def __init__(self, data: dict | None):
        self._data = data

    def table(self, *_args, **_kwargs):
        return self

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return None if self._data is None else FakeResult(data=self._data)


def make_token(secret: str, **claims) -> str:
    return jwt.encode({"aud": "authenticated", **claims}, secret, algorithm="HS256")


async def test_missing_authorization_header_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization="")
    assert exc_info.value.status_code == 401


async def test_malformed_token_is_rejected(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization="Bearer not-a-real-jwt")
    assert exc_info.value.status_code == 401


async def test_token_signed_with_wrong_secret_is_rejected(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    token = make_token("wrong-secret", sub="user-1")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


async def test_valid_token_without_profile_returns_404(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(auth, "get_db", lambda: FakeQuery(data=None))
    token = make_token("test-secret", sub="user-1")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 404


async def test_valid_token_with_profile_resolves_household(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(auth, "get_db", lambda: FakeQuery(data={"household_id": 42}))
    token = make_token("test-secret", sub="user-1")

    current_user = await auth.get_current_user(authorization=f"Bearer {token}")
    assert current_user.user_id == "user-1"
    assert current_user.household_id == 42
