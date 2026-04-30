"""/api/v1/voice — серверный STT через Yandex SpeechKit.

Мобилка пишет голос пакетом ``record`` (AAC/M4A или другой удобный кодек),
шлёт сюда multipart. Бэк через ffmpeg нормализует в OggOpus (формат, который
Yandex принимает) и распознаёт.

Альтернатива — гонять PCM напрямую (Yandex принимает LPCM), но для 5-минутных
записей это 10+ МБ. С Opus получаем 200 КБ/мин при том же качестве.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.db.models import User
from src.services.stt import recognize_speech_yandex

from .dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 12 * 1024 * 1024  # 12 МБ


class RecognizeOut(BaseModel):
    text: str
    duration_sec: float
    bytes: int


def _to_ogg_opus(data: bytes) -> bytes | None:
    """Конвертация любого аудио в OggOpus 48k mono 64kbps через ffmpeg."""
    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
            f.write(data)
            in_path = f.name
        out_path = in_path + ".ogg"
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", in_path,
                "-c:a", "libopus", "-b:a", "64k",
                "-ar", "48000", "-ac", "1",
                out_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            logger.warning("ffmpeg failed: %s", proc.stderr.decode("utf-8", "replace")[:300])
            return None
        with open(out_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("ffmpeg not installed on host")
        return None
    except Exception:
        logger.exception("ffmpeg conversion failed")
        return None
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


@router.post("/recognize", response_model=RecognizeOut)
async def recognize_voice(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> RecognizeOut:
    started = time.monotonic()
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Пустой файл")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Аудио слишком большое")

    # Yandex принимает только oggopus / lpcm. Нормализуем через ffmpeg.
    ogg = _to_ogg_opus(data) if not (audio.content_type or "").endswith("ogg") else data
    if ogg is None:
        # ffmpeg упал — попробуем напрямую (вдруг это уже ogg).
        ogg = data

    text = await recognize_speech_yandex(ogg)
    elapsed = time.monotonic() - started
    if text is None:
        logger.warning(
            "voice/recognize: STT returned None for user=%s (in=%dB, ogg=%dB, %.2fs)",
            user.id, len(data), len(ogg), elapsed,
        )
        return RecognizeOut(text="", duration_sec=elapsed, bytes=len(data))
    logger.info(
        "voice/recognize: user=%s in=%dB ogg=%dB elapsed=%.2fs len=%d",
        user.id, len(data), len(ogg), elapsed, len(text),
    )
    return RecognizeOut(text=text, duration_sec=elapsed, bytes=len(data))
