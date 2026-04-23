"""Unit-тесты MomentService: pipeline создания через skip-LLM + fallback.

Используем ту же in-memory fake AsyncSession, что в test_auth_api.py, но
упрощённую — нужны только User и Moment. Тяжёлое интеграционное тестирование
(JSONB, pgvector, курсор) выносится в integration-suite, которая требует
живой Postgres.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid as uuid_module
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from src.db.models import Moment, User
from src.services.llm_router.base import LLMResponse, LLMRouter, LLMTask, ProviderConfig
from src.services.llm_router.usage import InMemoryUsageLogger
from src.services.moments import MomentService
from src.services.moments.service import (
    MomentCreate,
    MomentForbidden,
    MomentNotFound,
    MomentPatch,
)


# --- helpers ---------------------------------------------------------------


def _make_user(
    id: int = 1, *, email: str = "u@example.com", is_pro_until: Optional[dt.datetime] = None
) -> User:
    u = User(
        email=email,
        password_hash="fake",
        display_name="U",
        timezone="Europe/Moscow",
        locale="ru",
        digest_hour=8,
        pro_until=is_pro_until,
    )
    u.id = id
    u.created_at = dt.datetime.now(dt.timezone.utc)
    return u


class _StubProvider:
    def __init__(self, json_content: str) -> None:
        self.json_content = json_content
        self.calls = 0

    async def chat(self, **_: Any) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content=self.json_content,
            provider="stub",
            model="stub-v1",
            input_tokens=50,
            output_tokens=100,
        )


def _make_router(json_content: str) -> tuple[LLMRouter, _StubProvider]:
    from decimal import Decimal

    stub = _StubProvider(json_content)
    router = LLMRouter(
        providers_by_task={
            LLMTask.FACET_EXTRACT: [
                ProviderConfig(
                    name="stub",
                    provider=stub,
                    model="stub-v1",
                    price_per_mtok_input_rub=Decimal("10"),
                    price_per_mtok_output_rub=Decimal("30"),
                )
            ]
        },
        usage_logger=InMemoryUsageLogger(),
    )
    return router, stub


@dataclass
class _FakeSession:
    """Упрощённая in-memory сессия только для моментов + юзеров."""

    moments: list[Moment] = field(default_factory=list)
    users: list[User] = field(default_factory=list)
    _next_id: int = 1

    async def scalar(self, stmt: Any) -> Any:
        """Для client_id lookup парсим BindParameter-ы из WHERE прямо через
        SA API — не трогая text-рендер (UUID там кодируется по-разному)."""
        from sqlalchemy.sql import Select
        from sqlalchemy.sql.elements import BinaryExpression, BindParameter

        if not isinstance(stmt, Select):
            return None
        where = stmt.whereclause
        if where is None:
            return None

        # Собираем пары (column_name, value) из всех бинарных сравнений.
        comparisons: dict[str, Any] = {}

        def _collect(node: Any) -> None:
            if isinstance(node, BinaryExpression):
                left, right = node.left, node.right
                if hasattr(left, "key") and isinstance(right, BindParameter):
                    comparisons[left.key] = right.value
                if hasattr(right, "key") and isinstance(left, BindParameter):
                    comparisons[right.key] = left.value
            for child in getattr(node, "get_children", lambda: [])():
                _collect(child)

        _collect(where)

        if "client_id" in comparisons:
            needle = str(comparisons["client_id"])
            for m in self.moments:
                if m.client_id is not None and str(m.client_id) == needle:
                    return m
        return None

    async def scalars(self, stmt: Any) -> "_FakeScalarResult":
        # Очень упрощённо: возвращаем все active moments юзера.
        s = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        rows = self.moments[:]
        if "moments.status != 'trashed'" in s or "status = 'active'" in s:
            rows = [m for m in rows if m.status not in {"trashed"}]
        if "moments.status = 'active'" in s:
            rows = [m for m in rows if m.status == "active"]
        if "moments.rrule IS NOT NULL" in s:
            rows = [m for m in rows if m.rrule]
        return _FakeScalarResult(rows)

    async def get(self, model: Any, pk: Any) -> Any:
        if model is Moment:
            for m in self.moments:
                if m.id == pk:
                    return m
        if model is User:
            for u in self.users:
                if u.id == pk:
                    return u
        return None

    def add(self, inst: Any) -> None:
        if isinstance(inst, Moment):
            self.moments.append(inst)
        elif isinstance(inst, User):
            self.users.append(inst)

    async def flush(self) -> None:
        for m in self.moments:
            if m.id is None:
                m.id = self._next_id
                self._next_id += 1
            if m.created_at is None:
                m.created_at = dt.datetime.now(dt.timezone.utc)
            if m.updated_at is None:
                m.updated_at = dt.datetime.now(dt.timezone.utc)

    async def commit(self) -> None:
        await self.flush()

    async def rollback(self) -> None:
        return None


class _FakeScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


@pytest.fixture
def session() -> _FakeSession:
    return _FakeSession()


@pytest.fixture
def user() -> User:
    return _make_user()


# --- tests: skip-LLM path --------------------------------------------------


class TestCreateSkipLLM:
    async def test_short_text_uses_heuristic_no_llm_call(
        self, session: _FakeSession, user: User
    ) -> None:
        router, stub = _make_router('{"kind":"note"}')
        svc = MomentService(session, llm_router=router)

        m = await svc.create_from_text(
            user, MomentCreate(raw_text="купить молоко", source="text")
        )
        assert m.title.startswith("Купить")
        assert m.facets["kind"] == "shopping"
        assert m.llm_version is None  # heuristic-путь
        assert stub.calls == 0        # LLM не вызывался

    async def test_saves_to_session(
        self, session: _FakeSession, user: User
    ) -> None:
        svc = MomentService(session)
        await svc.create_from_text(
            user, MomentCreate(raw_text="позвонить маме")
        )
        assert len(session.moments) == 1
        assert session.moments[0].user_id == user.id
        assert session.moments[0].id is not None


# --- tests: LLM path -------------------------------------------------------


class TestCreateLLM:
    async def test_long_text_calls_llm(
        self, session: _FakeSession, user: User
    ) -> None:
        payload = {
            "title": "позвонить Ане по договору",
            "summary": None,
            "kind": "task",
            "occurs_at": None,
            "rrule": None,
            "rrule_until": None,
            "people": ["Аня"],
            "places": [],
            "topics": ["работа"],
            "priority": "normal",
            "mood": None,
            "shopping_items": [],
        }
        router, stub = _make_router(json.dumps(payload))
        svc = MomentService(session, llm_router=router)

        m = await svc.create_from_text(
            user,
            MomentCreate(
                raw_text="надо не забыть обсудить с Аней наш договор и сроки",
            ),
        )
        assert stub.calls == 1
        assert m.title == "позвонить Ане по договору"
        assert m.facets["kind"] == "task"
        assert m.facets["people"] == ["Аня"]
        assert m.llm_version == "extract_facets_v1"

    async def test_llm_failure_falls_back_to_raw_title(
        self, session: _FakeSession, user: User
    ) -> None:
        from src.services.llm_router.base import LLMRouter

        empty_router = LLMRouter(providers_by_task={}, usage_logger=None)
        svc = MomentService(session, llm_router=empty_router)

        m = await svc.create_from_text(
            user,
            MomentCreate(raw_text="сложный текст без триггеров эвристики"),
        )
        # Ожидаем fallback: title из первой строки
        assert m.facets["kind"] == "note"
        assert "сложный текст" in m.title
        assert m.llm_version is None  # не смогли вызвать LLM

    async def test_summary_only_when_long(
        self, session: _FakeSession, user: User
    ) -> None:
        payload = {
            "title": "длинный заголовок",
            "summary": "Это обобщение текста",
            "kind": "note",
            "occurs_at": None,
            "rrule": None,
            "rrule_until": None,
            "people": [],
            "places": [],
            "topics": [],
            "priority": "normal",
            "mood": None,
            "shopping_items": [],
        }
        router, _ = _make_router(json.dumps(payload))
        svc = MomentService(session, llm_router=router)

        short = await svc.create_from_text(
            user, MomentCreate(raw_text="x" * 50 + " тригер отсутствует")
        )
        assert short.summary is None

        long_raw = "x" * 250
        long_m = await svc.create_from_text(user, MomentCreate(raw_text=long_raw))
        assert long_m.summary == "Это обобщение текста"


# --- tests: idempotency & patch & status ----------------------------------


class TestIdempotency:
    async def test_same_client_id_returns_existing(
        self, session: _FakeSession, user: User
    ) -> None:
        svc = MomentService(session)
        cid = uuid_module.uuid4()
        first = await svc.create_from_text(
            user, MomentCreate(raw_text="купить молоко", client_id=cid)
        )
        second = await svc.create_from_text(
            user, MomentCreate(raw_text="позвонить маме", client_id=cid)
        )
        assert first.id == second.id
        assert len(session.moments) == 1
        # Текст второго вызова НЕ затёр первый
        assert second.raw_text == "купить молоко"


class TestPatchAndLifecycle:
    async def test_patch_title(
        self, session: _FakeSession, user: User
    ) -> None:
        svc = MomentService(session)
        m = await svc.create_from_text(user, MomentCreate(raw_text="позвонить маме"))

        patched = await svc.patch(user, m.id, MomentPatch(title="Новый заголовок"))
        assert patched.title == "Новый заголовок"

    async def test_complete_sets_status_and_ts(
        self, session: _FakeSession, user: User
    ) -> None:
        svc = MomentService(session)
        m = await svc.create_from_text(user, MomentCreate(raw_text="позвонить маме"))

        done = await svc.complete(user, m.id)
        assert done.status == "done"
        assert done.completed_at is not None

    async def test_snooze_pushes_occurs_at(
        self, session: _FakeSession, user: User
    ) -> None:
        svc = MomentService(session)
        m = await svc.create_from_text(user, MomentCreate(raw_text="позвонить маме"))

        until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)
        snoozed = await svc.snooze(user, m.id, until)
        assert snoozed.occurs_at == until
        assert snoozed.status == "active"

    async def test_soft_delete_marks_trashed(
        self, session: _FakeSession, user: User
    ) -> None:
        svc = MomentService(session)
        m = await svc.create_from_text(user, MomentCreate(raw_text="позвонить маме"))

        await svc.soft_delete(user, m.id)
        assert m.status == "trashed"

        # Повторный get должен упасть
        with pytest.raises(MomentNotFound):
            await svc.get(user, m.id)

    async def test_get_other_users_moment_forbidden(
        self, session: _FakeSession, user: User
    ) -> None:
        other = _make_user(id=999)
        svc = MomentService(session)
        m = await svc.create_from_text(user, MomentCreate(raw_text="позвонить маме"))

        with pytest.raises(MomentForbidden):
            await svc.get(other, m.id)


class TestOverrides:
    async def test_client_occurs_at_beats_llm(
        self, session: _FakeSession, user: User
    ) -> None:
        payload = {
            "title": "созвон",
            "summary": None,
            "kind": "task",
            "occurs_at": "2099-01-01T00:00:00+00:00",  # LLM-значение
            "rrule": None,
            "rrule_until": None,
            "people": [],
            "places": [],
            "topics": [],
            "priority": "normal",
            "mood": None,
            "shopping_items": [],
        }
        router, _ = _make_router(json.dumps(payload))
        svc = MomentService(session, llm_router=router)

        override = dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc)
        m = await svc.create_from_text(
            user,
            MomentCreate(raw_text="созвон", occurs_at_override=override),
        )
        assert m.occurs_at == override
