"""Векторизация текстов через self-hosted multilingual-e5-small (fastembed/onnx).

384-мерные эмбеддинги, CPU, без внешних ключей. Модель ~120MB качается
автоматически на первое использование, кэшируется в ``~/.cache/fastembed``.

Когда поднимем self-hosted BGE-M3 на Hetzner (M3) — заменим внутренности,
интерфейс ``embed_text`` останется тот же.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

ModelKind = Literal["doc", "query"]

_model = None
_lock = asyncio.Lock()


async def _ensure_model():
    global _model
    if _model is not None:
        return _model
    async with _lock:
        if _model is not None:
            return _model
        # ленивый импорт — fastembed тяжёлая зависимость, не нужна для tests
        from fastembed import TextEmbedding

        loop = asyncio.get_running_loop()
        _model = await loop.run_in_executor(
            None, lambda: TextEmbedding(model_name=_MODEL_NAME)
        )
        logger.info("fastembed model loaded: %s", _MODEL_NAME)
        return _model


def _prefix(text: str, kind: ModelKind) -> str:
    # paraphrase-multilingual-MiniLM-L12-v2 не требует префиксов.
    return text


async def embed_text(
    text: str, *, kind: ModelKind = "doc"
) -> list[float] | None:
    """384-мерный вектор. None если текст пустой или модель упала."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        model = await _ensure_model()
        prefixed = _prefix(text[:8000], kind)
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(
            None, lambda: list(model.embed([prefixed]))
        )
        if not vectors:
            return None
        vec = vectors[0]
        # numpy.ndarray → list[float]
        if hasattr(vec, "tolist"):
            return [float(x) for x in vec.tolist()]
        return [float(x) for x in vec]
    except Exception:
        logger.exception("embed_text failed")
        return None
