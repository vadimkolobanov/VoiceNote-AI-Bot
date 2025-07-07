# src/services/stt.py
import json
import logging
import asyncio
import aiohttp
import ssl
import certifi

from ..core.config import YANDEX_SPEECHKIT_API_KEY, YANDEX_SPEECHKIT_FOLDER_ID

logger = logging.getLogger(__name__)

YANDEX_STT_API_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"

# --- Утилиты для работы с аудио ---

async def download_audio_content(audio_url: str) -> bytes | None:
    """Асинхронно скачивает аудиофайл по URL."""
    logger.info("Начало загрузки аудио из: %s", audio_url)

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                    audio_url,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    logger.debug("Аудио успешно загружено. Размер: %d байт", len(content))
                    return content

                error_info = {
                    'status': response.status,
                    'headers': dict(response.headers),
                    'body': await response.text()
                }
                logger.error("Ошибка загрузки аудио: %s", json.dumps(error_info, indent=2))

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка при загрузке аудио: %s", str(e))
    except asyncio.TimeoutError:
        logger.error("Таймаут при загрузке аудио")
    except Exception as e:
        logger.exception("Неожиданная ошибка при загрузке аудио: %s", str(e))

    return None


# --- Основная логика STT ---

async def recognize_speech_yandex(audio_data: bytes) -> str | None:
    """
    Отправляет аудиоданные в Yandex SpeechKit API и возвращает распознанный текст.
    """
    if not YANDEX_SPEECHKIT_API_KEY or not YANDEX_SPEECHKIT_FOLDER_ID:
        logger.error("Пропуск распознавания: Yandex STT не сконфигурирован в .env")
        return None

    # Конфигурация SSL
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    headers = {
        "Authorization": f"Api-Key {YANDEX_SPEECHKIT_API_KEY}",
        "Content-Type": "audio/ogg"  # Telegram использует oggopus
    }

    params = {
        "folderId": YANDEX_SPEECHKIT_FOLDER_ID,
        "lang": "ru-RU",
        "format": "oggopus",
        "sampleRateHertz": 48000,
        "model": "general"  # Модель для общих сценариев
    }

    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            logger.debug("Отправка запроса в Yandex STT...")
            async with session.post(
                    YANDEX_STT_API_URL,
                    params=params,
                    headers=headers,
                    data=audio_data,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_text = await response.text()
                logger.debug("Ответ от STT: статус %d, тело: %s...", response.status, response_text[:200])

                if response.status == 200:
                    try:
                        result_json = await response.json()
                        if 'result' in result_json:
                            recognized_text = result_json['result'].strip()
                            logger.info("Успешное распознавание. Длина текста: %d символов", len(recognized_text))
                            return recognized_text
                        else:
                            logger.error("В ответе STT отсутствует ключ 'result'. Ответ: %s", result_json)
                    except json.JSONDecodeError:
                        logger.error("Ошибка декодирования JSON ответа от STT: %s", response_text)
                else:
                    error_info = {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'body': response_text
                    }
                    logger.error("Ошибка API Yandex STT: %s", json.dumps(error_info, indent=2))

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка при обращении к Yandex STT: %s", str(e))
    except asyncio.TimeoutError:
        logger.error("Таймаут запроса к Yandex STT")
    except Exception as e:
        logger.exception("Неожиданная ошибка в процессе распознавания речи: %s", str(e))

    return None