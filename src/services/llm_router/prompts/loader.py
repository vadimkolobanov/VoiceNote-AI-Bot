"""Загрузка и рендер Jinja-промптов из этого пакета.

Используется бизнес-слоем так:
    prompt = render("extract_facets", raw_text=..., timezone=..., ...)
    response = await router.chat(task=LLMTask.FACET_EXTRACT, system=..., user=prompt)

Версия промпта (значение переменной ``VERSION`` в заголовке) пишется в
``moments.llm_version`` — т. е. каждый момент знает, какая ревизия промпта
его обработала (§6.2).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        undefined=StrictUndefined,  # любая пропущенная переменная = ошибка
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(prompt_name: str, /, **context: Any) -> str:
    """Рендерит ``{prompt_name}.md`` с переданным контекстом."""
    template = _env().get_template(f"{prompt_name}.md")
    return template.render(**context)


def load_raw(prompt_name: str) -> str:
    """Читает исходник без рендеринга — удобно для тестов и дампа в логах."""
    return (PROMPTS_DIR / f"{prompt_name}.md").read_text(encoding="utf-8")
