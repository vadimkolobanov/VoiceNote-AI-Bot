import logging
import asyncio
from datetime import timedelta

from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic
from redis.asyncio import Redis
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .....core.config import ADMIN_TELEGRAM_ID, CHAT_URL
from .....services.cache_service import get_redis_client
from ...admin.handlers import IsAdmin
from ....common_utils.states import SupportStates

logger = logging.getLogger(__name__)
router = Router()

REPLY_KEY_PREFIX = "support_reply"
REPLY_KEY_TTL_SECONDS = int(timedelta(days=7).total_seconds())


@router.callback_query(F.data == "report_problem")
async def start_report_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(SupportStates.awaiting_report_message)
    await callback.message.edit_text(
        "Опишите вашу проблему или предложение одним сообщением. "
        "Можно прикрепить фото или видео.\n\n"
        "Для отмены нажмите /cancel."
    )
    await callback.answer()


@router.message(SupportStates.awaiting_report_message, Command("cancel"))
async def report_cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отправка отменена.")


@router.message(SupportStates.awaiting_report_message)
async def process_report_message_handler(message: types.Message, state: FSMContext):
    await state.clear()

    if not ADMIN_TELEGRAM_ID:
        await message.answer("К сожалению, функция отправки репортов временно недоступна.")
        logger.warning("Попытка отправить репорт при отсутствующем ADMIN_TELEGRAM_ID.")
        return

    user = message.from_user
    info_text = (
        f"‼️ {hbold('Новый репорт о проблеме')}\n\n"
        f"От: {hitalic(user.full_name)}\n"
        f"Username: @{user.username if user.username else 'N/A'}\n"
        f"ID для ответа: `{user.id}`\n\n"
        f"Чтобы ответить, используйте функцию 'Ответить' на {hbold('ЭТО')} пересланное сообщение."
    )

    try:
        await message.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=info_text,
            parse_mode="HTML"
        )
        forwarded_message = await message.forward(chat_id=ADMIN_TELEGRAM_ID)

        redis: Redis = get_redis_client()
        redis_key = f"{REPLY_KEY_PREFIX}:{ADMIN_TELEGRAM_ID}:{forwarded_message.message_id}"
        await redis.set(redis_key, user.id, ex=REPLY_KEY_TTL_SECONDS)

        logger.info(
            f"Сохранен ключ для ответа в Redis: '{redis_key}' для пользователя {user.id} (TTL: {REPLY_KEY_TTL_SECONDS}s)")

        await message.answer("✅ Спасибо! Ваше сообщение отправлено администратору. Мы скоро с вами свяжемся.")

    except Exception as e:
        logger.error(f"Не удалось отправить репорт от {user.id} админу {ADMIN_TELEGRAM_ID}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.")


@router.message(IsAdmin(), F.reply_to_message)
async def admin_reply_handler(message: types.Message, bot: Bot, state: FSMContext):
    replied_to_message = message.reply_to_message

    if replied_to_message.forward_from is None and replied_to_message.forward_sender_name is None:
        logger.debug("Админ ответил не на пересланное сообщение. Игнорируем.")
        return

    admin_id = message.from_user.id
    message_id_to_find = replied_to_message.message_id

    redis: Redis = get_redis_client()
    redis_key = f"{REPLY_KEY_PREFIX}:{admin_id}:{message_id_to_find}"
    user_id_bytes = await redis.get(redis_key)

    if not user_id_bytes:
        logger.warning(
            f"Не удалось найти ID пользователя в Redis по ключу '{redis_key}'. "
            f"Возможно, ключ истёк или это очень старое сообщение."
        )
        await message.reply(
            "Не удалось определить получателя. Возможно, это старое сообщение или бот был перезапущен. "
            "Пожалуйста, свяжитесь с пользователем по его ID напрямую."
        )
        return

    user_id_to_reply = int(user_id_bytes.decode())

    try:

        bot_link = f"{CHAT_URL}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Перейти в чат с ботом", url=bot_link)]
        ])

        await bot.send_message(
            chat_id=user_id_to_reply,
            text=f"✉️ {hbold('Ответ от администратора:')}"
        )
        await message.copy_to(chat_id=user_id_to_reply, reply_markup=keyboard)

        await message.reply("✅ Ваш ответ успешно отправлен пользователю.")

        await redis.delete(redis_key)
        logger.info(f"Очищен ключ '{redis_key}' из Redis после ответа.")

    except Exception as e:
        logger.error(f"Не удалось отправить ответ от админа пользователю {user_id_to_reply}: {e}", exc_info=True)
        await message.reply(f"❌ Не удалось отправить ответ. Ошибка: {e}")