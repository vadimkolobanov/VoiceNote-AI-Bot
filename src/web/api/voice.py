# src/web/api/voice.py
import logging
import subprocess
import tempfile
import os

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel

from src.services.stt import recognize_speech_yandex
from src.bot.modules.notes.services import process_and_save_note
from src.database import user_repo
from src.core.config import YANDEX_STT_CONFIGURED, MAX_DAILY_STT_RECOGNITIONS_MVP
from .dependencies import get_current_user
from .schemas import Note

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_AUDIO_TYPES = {
    "audio/ogg", "audio/mpeg", "audio/mp4", "audio/m4a",
    "audio/x-m4a", "audio/aac", "audio/wav", "audio/webm",
    "application/octet-stream",  # некоторые клиенты не ставят content-type
}
MAX_AUDIO_SIZE_MB = 10


async def _convert_to_ogg_opus(audio_data: bytes, original_ext: str) -> bytes | None:
    """Конвертирует аудио в OGG Opus через ffmpeg (для Yandex SpeechKit)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{original_ext}", delete=False) as input_file:
            input_file.write(audio_data)
            input_path = input_file.name

        output_path = input_path.rsplit(".", 1)[0] + ".ogg"

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-c:a", "libopus", "-b:a", "64k",
                "-ar", "48000", "-ac", "1",
                output_path
            ],
            capture_output=True, timeout=30
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr.decode()}")
            return None

        with open(output_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("ffmpeg not found. Install ffmpeg for audio conversion.")
        return None
    except Exception as e:
        logger.error(f"Audio conversion error: {e}")
        return None
    finally:
        for path in [input_path, output_path]:
            if os.path.exists(path):
                os.unlink(path)


@router.post("/recognize", response_model=Note, tags=["Voice"])
async def recognize_voice_and_create_note(
        audio: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
):
    """
    Загружает аудиофайл, распознаёт речь и создаёт заметку.
    Поддерживает форматы: OGG, M4A, AAC, MP3, WAV, WebM.
    """
    if not YANDEX_STT_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech recognition service is not configured."
        )

    user_id = current_user['telegram_id']
    is_vip = current_user.get('is_vip', False)

    # Проверка лимита STT для бесплатных юзеров
    if not is_vip:
        stt_count = current_user.get('daily_stt_recognitions_count', 0)
        if stt_count >= MAX_DAILY_STT_RECOGNITIONS_MVP:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily voice recognition limit ({MAX_DAILY_STT_RECOGNITIONS_MVP}) reached."
            )

    # Читаем файл
    audio_data = await audio.read()
    file_size_mb = len(audio_data) / (1024 * 1024)
    if file_size_mb > MAX_AUDIO_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file too large. Maximum: {MAX_AUDIO_SIZE_MB}MB."
        )

    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file."
        )

    # Определяем формат и конвертируем если нужно
    content_type = audio.content_type or ""
    filename = audio.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    is_ogg = content_type == "audio/ogg" or ext == "ogg"

    if not is_ogg:
        logger.info(f"Converting audio from {content_type}/{ext} to OGG Opus for user {user_id}")
        audio_data = await _convert_to_ogg_opus(audio_data, ext or "m4a")
        if audio_data is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to convert audio format. Ensure ffmpeg is installed on the server."
            )

    # Распознаём речь
    recognized_text = await recognize_speech_yandex(audio_data)
    if not recognized_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not recognize speech from audio."
        )

    # Увеличиваем счётчик STT
    await user_repo.increment_stt_count(user_id)

    # Создаём заметку через существующий сервис
    user_tz = current_user.get('timezone', 'UTC')
    result = await process_and_save_note(
        telegram_id=user_id,
        raw_text=recognized_text,
        user_timezone_str=user_tz,
        is_vip=is_vip,
        bot=None  # Нет бота — не создаём напоминание через scheduler (мобилка использует push)
    )

    if not result or 'note_id' not in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create note from recognized text."
        )

    # Возвращаем созданную заметку
    from src.database import note_repo
    note = await note_repo.get_note_by_id(result['note_id'])
    if not note:
        raise HTTPException(status_code=500, detail="Note created but could not be retrieved.")

    return {
        "note_id": note['note_id'],
        "owner_id": note['telegram_id'],
        "summary_text": note.get('summary_text'),
        "corrected_text": note['corrected_text'],
        "category": note.get('category'),
        "created_at": note['created_at'],
        "updated_at": note['updated_at'],
        "note_taken_at": note.get('note_taken_at'),
        "due_date": note.get('due_date'),
        "recurrence_rule": note.get('recurrence_rule'),
        "is_archived": note.get('is_archived', False),
        "is_completed": note.get('is_completed', False),
        "llm_analysis_json": note.get('llm_analysis_json'),
    }
