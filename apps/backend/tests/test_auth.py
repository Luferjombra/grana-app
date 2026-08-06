from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
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


@dataclass
class FakeSigningKey:
    key: object


class FakeJwksClient:
    def __init__(self, key):
        self._key = key

    def get_signing_key_from_jwt(self, _token):
        return FakeSigningKey(key=self._key)


def make_key_pair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def make_token(private_key, **claims) -> str:
    return jwt.encode({"aud": "authenticated", **claims}, private_key, algorithm="ES256")


async def test_missing_authorization_header_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization="")
    assert exc_info.value.status_code == 401


async def test_malformed_token_is_rejected(monkeypatch):
    _, public_key = make_key_pair()
    monkeypatch.setattr(auth, "get_jwks_client", lambda: FakeJwksClient(public_key))

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization="Bearer not-a-real-jwt")
    assert exc_info.value.status_code == 401


async def test_token_signed_with_wrong_key_is_rejected(monkeypatch):
    attacker_private_key, _ = make_key_pair()
    _, legit_public_key = make_key_pair()
    monkeypatch.setattr(auth, "get_jwks_client", lambda: FakeJwksClient(legit_public_key))
    token = make_token(attacker_private_key, sub="user-1")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


async def test_valid_token_without_profile_returns_404(monkeypatch):
    private_key, public_key = make_key_pair()
    monkeypatch.setattr(auth, "get_jwks_client", lambda: FakeJwksClient(public_key))
    monkeypatch.setattr(auth, "get_db", lambda: FakeQuery(data=None))
    token = make_token(private_key, sub="user-1")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 404


async def test_valid_token_with_profile_resolves_household(monkeypatch):
    private_key, public_key = make_key_pair()
    monkeypatch.setattr(auth, "get_jwks_client", lambda: FakeJwksClient(public_key))
    monkeypatch.setattr(auth, "get_db", lambda: FakeQuery(data={"household_id": 42}))
    token = make_token(private_key, sub="user-1")

    current_user = await auth.get_current_user(authorization=f"Bearer {token}")
    assert current_user.user_id == "user-1"
    assert current_user.household_id == 42


async def test_hs256_token_is_rejected(monkeypatch):
    """Algoritmo simétrico não é aceito — evita ataque de algorithm confusion
    em que a chave pública do JWKS seria usada como segredo HMAC."""
    _, public_key = make_key_pair()
    monkeypatch.setattr(auth, "get_jwks_client", lambda: FakeJwksClient(public_key))
    token = jwt.encode({"aud": "authenticated", "sub": "user-1"}, "secret", algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401
