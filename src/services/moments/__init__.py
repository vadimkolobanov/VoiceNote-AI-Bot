"""Moments — доменный сервис единой сущности проекта (§4.1 + §6.1).

Точки входа бизнес-логики:
    create_from_text  — идёт через skip-LLM ? fallback на LLM-экстракт.
    list_*            — view-запросы (today/timeline/rhythm).
    update / complete / snooze / soft_delete — модификации.
    bulk_create       — офлайн-синк (§4.10).

Ничего про FastAPI/HTTP здесь нет — это слой domain, не transport.
"""
from .heuristics import classify_trivial_text, TrivialResult  # noqa: F401
from .service import MomentService  # noqa: F401
