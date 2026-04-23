"""Unit-тесты для src.services.security (PRODUCT_PLAN.md §10.1).

Без БД: только чистые функции argon2id + JWT.
"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

from src.services import security


class TestArgon2:
    def test_hash_roundtrip_matches(self) -> None:
        h = security.hash_password("correct horse battery staple")
        assert security.verify_password("correct horse battery staple", h) is True

    def test_hash_rejects_wrong_password(self) -> None:
        h = security.hash_password("letmein")
        assert security.verify_password("letmeout", h) is False

    def test_hash_rejects_garbage_hash(self) -> None:
        # Повреждённый хэш не должен ронять процесс — только вернуть False.
        assert security.verify_password("anything", "$argon2id$not-a-hash") is False

    def test_hash_is_not_plaintext(self) -> None:
        pwd = "mysecretpassword"
        h = security.hash_password(pwd)
        assert pwd not in h
        assert h.startswith("$argon2id$")

    def test_hash_is_unique_per_call(self) -> None:
        """Соль рандомная — один и тот же пароль даёт разные хэши."""
        h1 = security.hash_password("same")
        h2 = security.hash_password("same")
        assert h1 != h2
        assert security.verify_password("same", h1)
        assert security.verify_password("same", h2)


class TestJWT:
    def test_access_token_roundtrip(self) -> None:
        tok = security.create_access_token(42)
        assert security.decode_access_token(tok) == 42

    def test_access_token_expired(self) -> None:
        tok = security.create_access_token(
            1, expires_delta=timedelta(seconds=-10)
        )
        assert security.decode_access_token(tok) is None

    def test_refuses_wrong_type(self) -> None:
        """Ручной refresh-like токен не пройдёт как access."""
        from datetime import datetime, timezone

        from jose import jwt

        from src.core.config import JWT_ALGORITHM, JWT_SECRET_KEY

        payload = {
            "sub": "7",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "type": "refresh",  # не "access"
        }
        tok = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        assert security.decode_access_token(tok) is None

    def test_rejects_garbage_token(self) -> None:
        assert security.decode_access_token("not.a.jwt") is None
        assert security.decode_access_token("") is None

    def test_rejects_non_integer_sub(self) -> None:
        from datetime import datetime, timezone

        from jose import jwt

        from src.core.config import JWT_ALGORITHM, JWT_SECRET_KEY

        payload = {
            "sub": "not-an-int",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "type": "access",
        }
        tok = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        assert security.decode_access_token(tok) is None


class TestRefreshTokenHash:
    def test_deterministic(self) -> None:
        assert security.hash_refresh_token("abc") == security.hash_refresh_token("abc")

    def test_different_for_different_inputs(self) -> None:
        assert security.hash_refresh_token("abc") != security.hash_refresh_token("abd")

    def test_hash_length(self) -> None:
        # SHA-256 hex digest = 64 символа
        assert len(security.hash_refresh_token("whatever")) == 64
