# alice_webhook.py
import logging
import secrets
import string
import os
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


# Модели данных Pydantic остаются без изменений
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


bot_instance: Bot | None = None


def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot


@app.post("/alice_webhook")
async def handle_alice_request(request: AliceRequest):  # <-- Убрали 'authorization: str = Header(None)'

    # --- ЭТОТ БЛОК ПОЛНОСТЬЮ УДАЛЯЕМ ---
    # if ALICE_SECRET_TOKEN:
    #     expected_header = f"Bearer {ALICE_SECRET_TOKEN}"
    #     if not authorization or authorization != expected_header:
    #         logger.warning(f"Unauthorized access attempt. Got header: '{authorization}', expected: '{expected_header}'")
    #         raise HTTPException(status_code=403, detail="Forbidden")
    # ------------------------------------
    # Теперь любой запрос от Яндекса будет обработан.

    # Вся остальная логика функции остается без изменений
    alice_user_id = request.session.user.user_id
    utterance = request.request.original_utterance.lower()

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

    user = await db.find_user_by_alice_id(alice_user_id)
    if not user:
        return AliceResponse(response={
            "text": "Похоже, мы не знакомы. Для привязки аккаунта зайдите в Telegram-бот, в 'Профиле' откройте 'Настройки' и нажмите 'Привязать Яндекс.Алису', чтобы получить код активации."})

    if not bot_instance:
        return AliceResponse(response={"text": "Внутренняя ошибка сервера. Не могу связаться с Telegram."})

    success, message, new_note = await process_and_save_note(bot_instance, user['telegram_id'],
                                                             request.request.original_utterance)

    if success and new_note:
        await bot_instance.send_message(user['telegram_id'],
                                        f"🎙️ Заметка из Алисы сохранена:\n\n`{new_note['corrected_text']}`",
                                        parse_mode="Markdown")
        return AliceResponse(response={"text": "Готово, сохранила."})
    else:
        return AliceResponse(response={"text": f"К сожалению, не получилось. {message}"})


# Функции generate_activation_code и get_link_code_for_user остаются без изменений
def generate_activation_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_link_code_for_user(telegram_id: int) -> str:
    code = generate_activation_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    await db.set_alice_activation_code(telegram_id, code, expires_at)
    return code