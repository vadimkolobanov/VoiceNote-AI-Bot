# utills.py
import json
import logging
import os
import asyncio
import aiohttp
import certifi
import ssl

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ===== YANDEX STT CONFIG =====
YANDEX_STT_API_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class YandexSTTError(Exception):
    """Базовый класс для ошибок Yandex SpeechKit"""
    pass


async def validate_stt_config() -> bool:
    """Проверка конфигурации STT перед использованием"""
    required_vars = {
        'YANDEX_SPEECHKIT_API_KEY': os.getenv('YANDEX_SPEECHKIT_API_KEY'),
        'YANDEX_SPEECHKIT_FOLDER_ID': os.getenv('YANDEX_SPEECHKIT_FOLDER_ID')
    }

    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        logger.error(f"Ошибка конфигурации STT: отсутствуют переменные - {', '.join(missing)}")
        return False

    logger.debug("Проверка конфигурации Yandex STT успешна. API ключ: %s...",
                 os.getenv('YANDEX_SPEECHKIT_API_KEY')[:5])
    return True


async def recognize_speech_yandex(audio_data: bytes) -> str | None:
    """Распознавание речи через Yandex SpeechKit"""

    if not await validate_stt_config():
        logger.error("Пропуск распознавания: ошибки конфигурации")
        return None

    # Конфигурация SSL
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    headers = {
        "Authorization": f"Api-Key {os.getenv('YANDEX_SPEECHKIT_API_KEY')}",
        "Content-Type": "audio/ogg"
    }

    params = {
        "folderId": os.getenv('YANDEX_SPEECHKIT_FOLDER_ID'),
        "lang": "ru-RU",
        "format": "oggopus",
        "sampleRateHertz": 48000,
        "model": "general"
    }

    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            logger.debug("Начало запроса к STT с параметрами: %s", params)

            async with session.post(
                    YANDEX_STT_API_URL,
                    params=params,
                    headers=headers,
                    data=audio_data,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_text = await response.text()
                logger.debug("Ответ STT: статус %d, тело: %s",
                             response.status, response_text[:200])

                if response.status == 200:
                    try:
                        result = await response.json()
                        if 'result' in result:
                            logger.info("Успешное распознавание. Длина текста: %d символов",
                                        len(result['result']))
                            return result['result'].strip()
                        logger.error("В ответе STT отсутствует поле 'result'")
                    except json.JSONDecodeError:
                        logger.error("Ошибка декодирования JSON ответа")
                else:
                    error_info = {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'body': response_text
                    }
                    logger.error("Ошибка API STT: %s", json.dumps(error_info, indent=2))

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка STT: %s", str(e))
    except asyncio.TimeoutError:
        logger.error("Таймаут запроса к STT")
    except Exception as e:
        logger.exception("Неожиданная ошибка STT: %s", str(e))

    return None


async def download_audio_content(audio_url: str) -> bytes | None:
    """Скачивание аудио"""
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
        logger.error("Сетевая ошибка загрузки: %s", str(e))
    except asyncio.TimeoutError:
        logger.error("Таймаут загрузки аудио")
    except Exception as e:
        logger.exception("Неожиданная ошибка загрузки: %s", str(e))

    return None