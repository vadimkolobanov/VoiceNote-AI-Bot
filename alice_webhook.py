# alice_webhook.py
import logging
import secrets
import string
import os
import asyncio  # <-- Для фоновых задач
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel
from aiogram import Bot
from dotenv import load_dotenv

import database_setup as db
from services.note_creator import process_and_save_note

load_dotenv()
logger = logging.getLogger(__name__)
app = FastAPI(docs_url=None, redoc_url=None)


# --- Модели данных для Алисы (без изменений) ---
class AliceRequest(BaseModel):
    class Request(BaseModel):
        original_utterance: str

    class Session(BaseModel):
        class User(BaseModel):
            user_id: str

        user: User

    request: Request
    session: Session


class AliceResponse(BaseModel):
    class Response(BaseModel):
        text: str
        end_session: bool = True

    response: Response
    version: str = "1.0"


# --- Глобальная переменная для экземпляра бота (без изменений) ---
bot_instance: Bot | None = None


def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot


# --- НОВАЯ ФУНКЦИЯ ДЛЯ ФОНОВОЙ РАБОТЫ ---
async def process_note_in_background(user: dict, utterance: str):
    """
    Эта функция выполняется в фоне, не блокируя ответ Алисе.
    Она делает всю тяжелую работу.
    """
    logger.info(f"Background task started for user {user['telegram_id']}")
    try:
        if not bot_instance:
            logger.error("Bot instance is not set in background task!")
            return

        # Вызываем нашу основную сервисную функцию
        success, message, new_note = await process_and_save_note(
            bot=bot_instance,
            telegram_id=user['telegram_id'],
            text_to_process=utterance
        )

        # Отправляем результат пользователю в Telegram
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
        # Уведомляем пользователя о критической ошибке, если можем
        if bot_instance:
            await bot_instance.send_message(
                user['telegram_id'],
                "😔 Произошла критическая ошибка при обработке вашей заметки из Алисы."
            )


# --- КОНЕЦ НОВОЙ ФУНКЦИИ ---


@app.post("/alice_webhook")
async def handle_alice_request(request: AliceRequest):
    alice_user_id = request.session.user.user_id
    utterance = request.request.original_utterance.lower()

    # --- Блок активации кода (быстрый, поэтому остается без изменений) ---
    if utterance.startswith("активировать код"):
        code = utterance.replace("активировать код", "").strip().upper()
        if not code:
            return AliceResponse(response={"text": "Пожалуйста, назовите код полностью."})

        user_to_link = await db.find_user_by_alice_code(code)
        if not user_to_link:
            return AliceResponse(response={"text": "Код не найден или истёк. Получите новый в Telegram."})

        await db.link_alice_user(user_to_link['telegram_id'], alice_user_id)
        if bot_instance:
            await bot_instance.send_message(user_to_link['telegram_id'],
                                            "✅ Ваш аккаунт успешно привязан к Яндекс.Алисе!")
        return AliceResponse(response={"text": "Отлично! Аккаунт привязан. Теперь скажите, что нужно запомнить."})

    # --- Блок проверки пользователя (быстрый, без изменений) ---
    user = await db.find_user_by_alice_id(alice_user_id)
    if not user:
        return AliceResponse(response={
            "text": "Похоже, мы не знакомы. Для привязки аккаунта зайдите в Telegram-бот, в 'Профиле' откройте 'Настройки' и нажмите 'Привязать Яндекс.Алису', чтобы получить код активации."})

    if not bot_instance:
        return AliceResponse(response={"text": "Внутренняя ошибка сервера. Не могу связаться с Telegram."})

    # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
    # 1. Запускаем долгую обработку в фоновой задаче
    asyncio.create_task(
        process_note_in_background(user, request.request.original_utterance)
    )

    # 2. Немедленно отвечаем Алисе, не дожидаясь результата
    return AliceResponse(response={"text": "Приняла! Результат отправлю в Telegram."})
    # ---------------------------


# --- Функции генерации кода (без изменений) ---
def generate_activation_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_link_code_for_user(telegram_id: int) -> str:
    code = generate_activation_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    await db.set_alice_activation_code(telegram_id, code, expires_at)
    return code