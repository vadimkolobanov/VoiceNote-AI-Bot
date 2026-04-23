"""Промпты для LLM-задач. Markdown + Jinja подстановки.

Структура каждого промпта:
    1. System-роль (кратко)
    2. Context — taimezone, дата, recent facts/titles
    3. Input — raw_text
    4. Output — строгий JSON-схема
    5. Few-shot — 6 примеров (по одному на каждый kind)
    6. @characterguide (тон)

Версия промпта пишется в ``moments.llm_version`` (§6.2).
"""
