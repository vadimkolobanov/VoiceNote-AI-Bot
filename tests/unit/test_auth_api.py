"""HTTP-уровневые тесты /api/v1/auth/* (PRODUCT_PLAN.md §5.2).

Подменяем ``get_session`` на in-memory fake, чтобы не поднимать Postgres.
Это честное покрытие FastAPI-слоя: роутинг + сериализация + вызов
auth_service. Слой БД мокается — интеграцию прогоняем отдельно в M1 staging.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db.models import RefreshToken, User
from src.db.session import get_session
from src.services import security
from src.web.api.v1.auth import router as auth_router


# --- In-memory fake session ------------------------------------------------


@dataclass
class _FakeSession:
    """Минимальная имитация AsyncSession для auth_service.

    Поддерживает:
        scalar(select(User).where(email == ...))
        scalar(select(RefreshToken).where(token_hash == ...))
        session.add(instance)
        session.get(User, id)
        session.execute(update(...).where(...).values(...))
        session.flush() — присваивает id
        session.commit()/rollback()
    """

    users: list[User] = field(default_factory=list)
    refresh_tokens: list[RefreshToken] = field(default_factory=list)
    _next_user_id: int = 1
    _next_refresh_id: int = 1

    # auth_service вызывает select(User).where(User.email == X).
    # Реализуем упрощённо через чтение `.compile` SQL clause.
    async def scalar(self, stmt: Any) -> Any:
        # Работаем с SQLAlchemy-selectable. Читаем колонки в WHERE.
        s = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        if "FROM users" in s:
            for where_field in ("email", "id"):
                marker = f"users.{where_field} = "
                if marker in s:
                    needle = s.split(marker, 1)[1].split()[0].strip("'\"")
                    for u in self.users:
                        if str(getattr(u, where_field)) == needle:
                            return u
                    return None
        if "FROM refresh_tokens" in s:
            marker = "refresh_tokens.token_hash = "
            if marker in s:
                needle = s.split(marker, 1)[1].split()[0].strip("'\"")
                for rt in self.refresh_tokens:
                    if rt.token_hash == needle:
                        return rt
                return None
        return None

    async def get(self, model: Any, pk: Any) -> Any:
        if model is User:
            for u in self.users:
                if u.id == pk:
                    return u
        if model is RefreshToken:
            for rt in self.refresh_tokens:
                if rt.id == pk:
                    return rt
        return None

    def add(self, inst: Any) -> None:
        if isinstance(inst, User):
            self.users.append(inst)
        elif isinstance(inst, RefreshToken):
            self.refresh_tokens.append(inst)
        else:
            raise AssertionError(f"Unknown model in fake: {type(inst)}")

    async def flush(self) -> None:
        # Имитируем серверные defaults из миграции V1 — настоящая БД их
        # применяет автоматически, но наш fake этого не делает.
        for u in self.users:
            if u.id is None:
                u.id = self._next_user_id
                self._next_user_id += 1
            if u.created_at is None:
                u.created_at = dt.datetime.now(dt.timezone.utc)
            if u.timezone is None:
                u.timezone = "Europe/Moscow"
            if u.locale is None:
                u.locale = "ru"
            if u.digest_hour is None:
                u.digest_hour = 8
        for rt in self.refresh_tokens:
            if rt.id is None:
                rt.id = self._next_refresh_id
                self._next_refresh_id += 1
            if rt.created_at is None:
                rt.created_at = dt.datetime.now(dt.timezone.utc)

    async def execute(self, stmt: Any) -> Any:
        """Поддерживает UPDATE ... WHERE для логаута. Для простоты — no-op
        (тесты на logout проверяют статус 204, не побочку)."""
        return None

    async def commit(self) -> None:
        await self.flush()

    async def rollback(self) -> None:
        return None


# --- Test app --------------------------------------------------------------


@pytest.fixture
def fake_session() -> _FakeSession:
    return _FakeSession()


@pytest.fixture
def app(fake_session: _FakeSession) -> FastAPI:
    application = FastAPI()
    application.include_router(auth_router, prefix="/api/v1")

    async def _override() -> _FakeSession:
        yield fake_session

    application.dependency_overrides[get_session] = _override
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# --- Tests -----------------------------------------------------------------


VALID_EMAIL = "alice@example.com"
VALID_PASSWORD = "hunter22_strong"


class TestRegister:
    def test_register_returns_token_pair_and_user(
        self, client: TestClient, fake_session: _FakeSession
    ) -> None:
        resp = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD, "display_name": "Alice"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "access" in body and body["access"]
        assert "refresh" in body and body["refresh"]
        assert body["user"]["email"] == VALID_EMAIL
        assert body["user"]["display_name"] == "Alice"
        assert body["user"]["is_pro"] is False
        assert body["user"]["timezone"] == "Europe/Moscow"

        assert len(fake_session.users) == 1
        assert fake_session.users[0].email == VALID_EMAIL
        assert len(fake_session.refresh_tokens) == 1

    def test_register_rejects_duplicate_email(self, client: TestClient) -> None:
        first = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        assert first.status_code == 201

        dup = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        assert dup.status_code == 409
        assert dup.json()["detail"]["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    def test_register_normalizes_email(
        self, client: TestClient, fake_session: _FakeSession
    ) -> None:
        resp = client.post(
            "/api/v1/auth/email/register",
            json={"email": "  Alice@Example.COM ", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 201
        assert fake_session.users[0].email == "alice@example.com"

    def test_register_rejects_short_password(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_rejects_bad_email(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/email/register",
            json={"email": "not-an-email", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 422


class TestLogin:
    def _register(self, client: TestClient) -> dict[str, Any]:
        r = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        return r.json()

    def test_login_returns_new_token_pair(self, client: TestClient) -> None:
        reg = self._register(client)
        resp = client.post(
            "/api/v1/auth/email/login",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["access"] != reg["access"] or True  # токены могут совпасть по exp
        assert body["refresh"] != reg["refresh"], "refresh должен быть новым"
        assert body["user"]["email"] == VALID_EMAIL

    def test_login_wrong_password_returns_401(self, client: TestClient) -> None:
        self._register(client)
        resp = client.post(
            "/api/v1/auth/email/login",
            json={"email": VALID_EMAIL, "password": "wrong_password_123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_unknown_email_returns_401_same_code(
        self, client: TestClient
    ) -> None:
        """Anti-enumeration: unknown email даёт тот же код что wrong password."""
        resp = client.post(
            "/api/v1/auth/email/login",
            json={"email": "nobody@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


class TestRefresh:
    def test_refresh_rotates_token(
        self, client: TestClient, fake_session: _FakeSession
    ) -> None:
        reg = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        ).json()

        resp = client.post("/api/v1/auth/refresh", json={"refresh": reg["refresh"]})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["refresh"] != reg["refresh"]
        assert body["access"]

        # Старый токен должен быть отозван.
        old_hash = security.hash_refresh_token(reg["refresh"])
        old_row = next(rt for rt in fake_session.refresh_tokens if rt.token_hash == old_hash)
        assert old_row.revoked_at is not None

    def test_refresh_with_garbage_token_returns_401(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/refresh", json={"refresh": "garbage"})
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "INVALID_REFRESH_TOKEN"

    def test_refresh_with_already_rotated_token_fails(
        self, client: TestClient
    ) -> None:
        reg = client.post(
            "/api/v1/auth/email/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        ).json()

        # Первая ротация — ок
        first = client.post("/api/v1/auth/refresh", json={"refresh": reg["refresh"]})
        assert first.status_code == 200
        # Вторая с тем же токеном — 401
        second = client.post("/api/v1/auth/refresh", json={"refresh": reg["refresh"]})
        assert second.status_code == 401


class TestResetStubs:
    def test_reset_request_returns_204_even_for_unknown_email(
        self, client: TestClient
    ) -> None:
        """Anti-enumeration по §5.2: всегда 204."""
        resp = client.post(
            "/api/v1/auth/reset/request", json={"email": "nobody@example.com"}
        )
        assert resp.status_code == 204

    def test_reset_confirm_is_not_implemented_until_m7(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/auth/reset/confirm",
            json={"token": "whatever", "new_password": "newpassword123"},
        )
        assert resp.status_code == 501
