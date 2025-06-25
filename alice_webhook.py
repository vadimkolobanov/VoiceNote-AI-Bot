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
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv

import database_setup as db
from services import note_creator

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(docs_url=None, redoc_url=None)


class AliceRequest(BaseModel):
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
    class Response(BaseModel):
        text: str
        end_session: bool = True
    response: Response
    version: str = "1.0"


bot_instance: Bot | None = None


def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot


async def process_note_in_background(user: dict, utterance: str):
    logger.info(f"Background task for Alice started for user {user['telegram_id']}")
    try:
        if not bot_instance:
            logger.error("Bot instance is not set in Alice background task!")
            return

        success, message, new_note = await note_creator.process_and_save_note(
            bot=bot_instance,
            telegram_id=user['telegram_id'],
            text_to_process=utterance
        )

        if success and new_note:
            await db.log_user_action(
                user['telegram_id'],
                'create_note_alice',
                {'note_id': new_note['note_id']}
            )
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
        logger.error(f"Error in background note processing from Alice for user {user['telegram_id']}: {e}", exc_info=True)
        if bot_instance:
            await bot_instance.send_message(
                user['telegram_id'],
                "😔 Произошла критическая ошибка при обработке вашей заметки из Алисы."
            )


def generate_activation_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_link_code_for_user(telegram_id: int) -> str:
    code = generate_activation_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    await db.set_alice_activation_code(telegram_id, code, expires_at)
    return code


@app.post("/alice_webhook")
async def handle_alice_request(request: AliceRequest):
    alice_user_id = request.session.user.user_id
    utterance = request.request.original_utterance.lower().strip("?!.,")

    if request.session.new:
        user = await db.find_user_by_alice_id(alice_user_id)
        if user:
            welcome_text = "Здравствуйте! Я готова создавать для вас заметки. Просто скажите, например: попроси VoiceNote напомнить мне купить хлеб."
        else:
            welcome_text = "Здравствуйте! Чтобы я могла сохранять ваши заметки, сначала нужно привязать ваш Telegram-аккаунт. Для этого получите код в боте и скажите мне: активировать код, и назовите его."
        return AliceResponse(response={"text": welcome_text, "end_session": False})

    help_commands = ["помощь", "что ты умеешь", "справка", "хелп", "что ты можешь"]
    if utterance in help_commands:
        help_text = "Я умею создавать для вас заметки и напоминания. Просто скажите мне, что нужно запомнить, например: попроси VoiceNote напомнить мне позвонить маме в семь вечера. Вся магия произойдет в вашем Telegram-боте. Для привязки аккаунта получите код в боте и скажите: активировать код, и назовите его."
        return AliceResponse(response={"text": help_text, "end_session": True})

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

    user = await db.find_user_by_alice_id(alice_user_id)
    if not user:
        return AliceResponse(response={
            "text": "Сначала нужно привязать ваш аккаунт. Скажите 'активировать код' и назовите код из Telegram-бота.",
            "end_session": False})

    if not bot_instance:
        logger.error("Bot instance is not configured in webhook handler!")
        return AliceResponse(response={"text": "Внутренняя ошибка сервера. Пожалуйста, попробуйте позже."})

    asyncio.create_task(
        process_note_in_background(user, request.request.original_utterance)
    )

    return AliceResponse(response={"text": "Приняла! Результат отправлю в Telegram."})