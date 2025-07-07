# src/web/routes.py
import asyncio
import logging
import secrets
import string
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.utils.markdown import hbold

from ..database import user_repo, note_repo
from ..bot.modules.notes.services import process_and_save_note
from .models import AliceRequest, AliceResponse

logger = logging.getLogger(__name__)

bot_instance: Bot | None = None


def set_bot_instance(bot: Bot):
    """Устанавливает глобальный экземпляр бота для использования в фоновых задачах."""
    global bot_instance
    bot_instance = bot


def generate_activation_code(length=6) -> str:
    """Генерирует случайный код активации."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_link_code_for_user(telegram_id: int) -> str:
    """Генерирует и сохраняет код привязки для пользователя."""
    code = generate_activation_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    await user_repo.set_alice_activation_code(telegram_id, code, expires_at)
    return code


async def process_note_in_background(user: dict, utterance: str):
    """Фоновая задача для обработки и сохранения заметки из Алисы."""
    logger.info(f"Background task for Alice started for user {user['telegram_id']}")
    if not bot_instance:
        logger.error("Bot instance is not set in Alice background task!")
        return

    try:
        success, message, new_note, _ = await process_and_save_note(
            bot=bot_instance,
            telegram_id=user['telegram_id'],
            text_to_process=utterance
        )

        if success and new_note:
            await user_repo.log_user_action(
                user['telegram_id'],
                'create_note_alice',
                {'note_id': new_note['note_id']}
            )
            await bot_instance.send_message(
                user['telegram_id'],
                f"🎙️ Заметка из Алисы сохранена:\n\n`{new_note.get('summary_text', new_note['corrected_text'])}`",
                parse_mode="Markdown"
            )
        else:
            await bot_instance.send_message(
                user['telegram_id'],
                f"😔 Не удалось сохранить заметку из Алисы.\nПричина: {message}"
            )
    except Exception as e:
        logger.error(f"Error in background note processing from Alice for user {user['telegram_id']}: {e}",
                     exc_info=True)
        if bot_instance:
            await bot_instance.send_message(user['telegram_id'],
                                            "😔 Произошла критическая ошибка при обработке заметки из Алисы.")


async def handle_alice_request(request: AliceRequest) -> AliceResponse:
    """Главный обработчик входящих запросов от Алисы."""
    alice_user_id = request.session.user.user_id
    utterance = request.request.original_utterance.lower().strip("?!.,")

    # Приветствие при запуске навыка
    if request.session.new:
        user = await user_repo.find_user_by_alice_id(alice_user_id)
        if user:
            welcome_text = "Здравствуйте! Я готова создавать для вас заметки. Просто скажите, что нужно запомнить."
        else:
            welcome_text = "Здравствуйте! Чтобы я могла сохранять ваши заметки, сначала привяжите ваш Telegram-аккаунт. Получите код в боте и скажите: активировать код, а затем назовите его."
        return AliceResponse(response={"text": welcome_text, "end_session": False})

    # Обработка команды активации
    if utterance.startswith("активировать код"):
        code = utterance.replace("активировать код", "").strip().upper()
        if not code:
            return AliceResponse(response={"text": "Пожалуйста, назовите код полностью.", "end_session": False})

        user_to_link = await user_repo.find_user_by_alice_code(code)
        if not user_to_link:
            return AliceResponse(
                response={"text": "Код не найден или истёк. Получите новый в Telegram.", "end_session": True})

        await user_repo.link_alice_user(user_to_link['telegram_id'], alice_user_id)
        if bot_instance:
            await bot_instance.send_message(user_to_link['telegram_id'],
                                            "✅ Ваш аккаунт успешно привязан к Яндекс.Алисе!")
        return AliceResponse(
            response={"text": "Отлично! Аккаунт привязан. Теперь вы можете создавать заметки.", "end_session": True})

    # Проверка, привязан ли пользователь
    user = await user_repo.find_user_by_alice_id(alice_user_id)
    if not user:
        return AliceResponse(response={
            "text": "Сначала нужно привязать ваш аккаунт. Скажите 'активировать код' и назовите код из Telegram-бота.",
            "end_session": False})

    if not bot_instance:
        logger.error("Bot instance is not configured in webhook handler!")
        return AliceResponse(response={"text": "Внутренняя ошибка сервера. Пожалуйста, попробуйте позже."})

    # Запускаем создание заметки в фоне, чтобы Алиса не ждала
    asyncio.create_task(
        process_note_in_background(user, request.request.original_utterance)
    )

    return AliceResponse(response={"text": "Приняла! Результат отправлю в Telegram."})