# alice_webhook.py
import logging
import secrets
import string
import os
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel
from aiogram import Bot
from dotenv import load_dotenv

import database_setup as db
from services.note_creator import process_and_save_note

# Загрузка переменных окружения из .env файла
load_dotenv()
logger = logging.getLogger(__name__)

# Инициализация FastAPI приложения без стандартной документации
app = FastAPI(docs_url=None, redoc_url=None)


# --- Модели данных для запросов и ответов от Алисы ---

class AliceRequest(BaseModel):
    """
    Структура входящего запроса от API Яндекс.Диалогов.
    """

    class Session(BaseModel):
        new: bool

        class User(BaseModel):
            user_id: str

        user: User

    class Request(BaseModel):
        original_utterance: str
        type: str

    request: Request
    session: Session


class AliceResponse(BaseModel):
    """
    Структура ответа, которую ожидает API Яндекс.Диалогов.
    """

    class Response(BaseModel):
        text: str
        end_session: bool = True

    response: Response
    version: str = "1.0"


# --- Глобальные переменные и утилиты ---

# Глобальная переменная для хранения экземпляра aiogram-бота
bot_instance: Bot | None = None


def set_bot_instance(bot: Bot):
    """
    Устанавливает глобальный экземпляр бота для использования в вебхуке.
    Это позволяет отправлять сообщения в Telegram из обработчиков FastAPI.
    """
    global bot_instance
    bot_instance = bot


async def process_note_in_background(user: dict, utterance: str):
    """
    Выполняет "тяжелую" операцию по созданию заметки в фоновом режиме,
    чтобы не задерживать быстрый ответ для API Алисы.
    """
    logger.info(f"Background task started for user {user['telegram_id']}")
    try:
        if not bot_instance:
            logger.error("Bot instance is not set in background task!")
            return

        # Вызов основной сервисной функции для создания заметки
        success, message, new_note = await process_and_save_note(
            bot=bot_instance,
            telegram_id=user['telegram_id'],
            text_to_process=utterance
        )

        # Отправка результата пользователю в Telegram
        if success and new_note:
            await bot_instance.send_message(
                user['telegram_id'],
                f"🎙️ Заметка из Алисы сохранена:\n\n`{new_note['corrected_text']}`",
                parse_mode="Markdown"
            )
        else:
            await bot_instance.send_message(
                user['telegram_id'],
                f"😔 Не удалось сохранить заметку из Алисы.\nПричина: {message}"
            )
    except Exception as e:
        logger.error(f"Error in background note processing for user {user['telegram_id']}: {e}", exc_info=True)
        if bot_instance:
            await bot_instance.send_message(
                user['telegram_id'],
                "😔 Произошла критическая ошибка при обработке вашей заметки из Алисы."
            )


def generate_activation_code(length=6):
    """Генерирует случайный буквенно-цифровой код для активации."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_link_code_for_user(telegram_id: int) -> str:
    """Генерирует, сохраняет в БД и возвращает код активации для пользователя."""
    code = generate_activation_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    await db.set_alice_activation_code(telegram_id, code, expires_at)
    return code


# --- Основной обработчик вебхука ---

@app.post("/alice_webhook")
async def handle_alice_request(request: AliceRequest):
    """
    Основная точка входа для всех запросов от Яндекс.Диалогов.
    """
    alice_user_id = request.session.user.user_id
    # Очищаем фразу пользователя для более надежного сравнения
    utterance = request.request.original_utterance.lower().strip("?!.,")

    # Обработка приветственного сообщения при первом запуске навыка в сессии
    if request.session.new:
        user = await db.find_user_by_alice_id(alice_user_id)
        if user:
            welcome_text = "Здравствуйте! Я готова создавать для вас заметки. Просто скажите, например: попроси VoiceNote напомнить мне купить хлеб."
        else:
            welcome_text = "Здравствуйте! Чтобы я могла сохранять ваши заметки, сначала нужно привязать ваш Telegram-аккаунт. Для этого получите код в боте и скажите мне: активировать код, и назовите его."
        # Не завершаем сессию, чтобы дать пользователю возможность сразу ответить
        return AliceResponse(response={"text": welcome_text, "end_session": False})

    # Обработка команд помощи
    help_commands = ["помощь", "что ты умеешь", "справка", "хелп", "что ты можешь"]
    if utterance in help_commands:
        help_text = "Я умею создавать для вас заметки и напоминания. Просто скажите мне, что нужно запомнить, например: попроси VoiceNote напомнить мне позвонить маме в семь вечера. Вся магия произойдет в вашем Telegram-боте. Для привязки аккаунта получите код в боте и скажите: активировать код, и назовите его."
        # Завершаем сессию после предоставления справки
        return AliceResponse(response={"text": help_text, "end_session": True})

    # Обработка активации по коду
    if utterance.startswith("активировать код"):
        code = utterance.replace("активировать код", "").strip().upper()
        if not code:
            return AliceResponse(response={"text": "Пожалуйста, назовите код полностью.", "end_session": False})

        user_to_link = await db.find_user_by_alice_code(code)
        if not user_to_link:
            return AliceResponse(
                response={"text": "Код не найден или истёк. Получите новый в Telegram.", "end_session": True})

        await db.link_alice_user(user_to_link['telegram_id'], alice_user_id)
        if bot_instance:
            await bot_instance.send_message(user_to_link['telegram_id'],
                                            "✅ Ваш аккаунт успешно привязан к Яндекс.Алисе!")
        return AliceResponse(
            response={"text": "Отлично! Аккаунт привязан. Теперь вы можете создавать заметки.", "end_session": True})

    # Проверка, привязан ли пользователь
    user = await db.find_user_by_alice_id(alice_user_id)
    if not user:
        # Если пользователь не привязан и команда не является активацией
        return AliceResponse(response={
            "text": "Сначала нужно привязать ваш аккаунт. Скажите 'активировать код' и назовите код из Telegram-бота.",
            "end_session": False})

    if not bot_instance:
        logger.error("Bot instance is not configured in webhook handler!")
        return AliceResponse(response={"text": "Внутренняя ошибка сервера. Пожалуйста, попробуйте позже."})

    # Если все проверки пройдены, создаем заметку
    asyncio.create_task(
        process_note_in_background(user, request.request.original_utterance)
    )

    # Немедленно отвечаем Алисе, не дожидаясь результата фоновой задачи
    return AliceResponse(response={"text": "Приняла! Результат отправлю в Telegram."})