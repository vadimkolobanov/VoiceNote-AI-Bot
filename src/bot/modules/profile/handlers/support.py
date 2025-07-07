# src/bot/modules/profile/handlers/support.py
import logging

from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic

from .....core.config import ADMIN_TELEGRAM_ID
from ...admin.handlers import IsAdmin  # Импортируем фильтр из админского модуля
from ..common_utils.states import SupportStates

logger = logging.getLogger(__name__)
router = Router()


# --- Хендлеры для пользователя ---

@router.callback_query(F.data == "report_problem")
async def start_report_handler(callback: types.CallbackQuery, state: FSMContext):
    """Начинает сценарий отправки репорта."""
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
    """Отменяет процесс отправки репорта."""
    await state.clear()
    await message.answer("Отправка отменена.")


@router.message(SupportStates.awaiting_report_message)
async def process_report_message_handler(message: types.Message, state: FSMContext):
    """
    Принимает сообщение от пользователя, пересылает его админу
    и сохраняет связь "сообщение-пользователь" для возможности ответа.
    """
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
        # Сначала отправляем информацию об отправителе
        await message.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=info_text,
            parse_mode="HTML"
        )
        # Затем пересылаем само сообщение. Оно будет ниже и на него удобнее отвечать.
        forwarded_message = await message.forward(chat_id=ADMIN_TELEGRAM_ID)

        # Сохраняем в FSM связку ID админа и ID пересланного сообщения с ID пользователя,
        # чтобы админ мог ответить на это сообщение.
        # Это надежнее, чем полагаться на `forward_from`.
        await state.storage.set_data(
            # Ключ состоит из ID чата (админа) и ID сообщения
            key=(str(ADMIN_TELEGRAM_ID), str(forwarded_message.message_id)),
            data={'user_id_to_reply': user.id}
        )
        logger.info(
            f"Сохранен ключ для ответа в FSM: {(str(ADMIN_TELEGRAM_ID), str(forwarded_message.message_id))} для пользователя {user.id}")

        await message.answer("✅ Спасибо! Ваше сообщение отправлено администратору. Мы скоро с вами свяжемся.")

    except Exception as e:
        logger.error(f"Не удалось отправить репорт от {user.id} админу {ADMIN_TELEGRAM_ID}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.")


# --- Хендлер для ответа администратора ---

@router.message(IsAdmin(), F.reply_to_message)
async def admin_reply_handler(message: types.Message, bot: Bot, state: FSMContext):
    """
    Ловит ответ администратора на пересланное сообщение и отправляет
    ответ пользователю, который отправил репорт.
    """
    replied_to_message = message.reply_to_message

    # Игнорируем, если админ отвечает не на пересланное сообщение
    if replied_to_message.forward_date is None:
        logger.debug("Админ ответил не на пересланное сообщение. Игнорируем.")
        return

    admin_id_str = str(message.from_user.id)
    message_id_str = str(replied_to_message.message_id)

    # Ищем ID пользователя для ответа в хранилище FSM по ключу (админ, сообщение)
    storage_data = await state.storage.get_data(
        key=(admin_id_str, message_id_str)
    )

    user_id_to_reply = storage_data.get('user_id_to_reply') if storage_data else None

    if not user_id_to_reply:
        logger.warning(
            f"Не удалось найти ID пользователя для ответа на сообщение {message_id_str}. "
            f"Возможно, FSM был очищен или это очень старое сообщение."
        )
        await message.reply(
            "Не удалось определить получателя. Возможно, это старое сообщение или бот был перезапущен. "
            "Пожалуйста, свяжитесь с пользователем по его ID напрямую."
        )
        return

    try:
        # Отправляем пользователю "обертку" и копию сообщения админа
        await bot.send_message(
            chat_id=user_id_to_reply,
            text=f"✉️ {hbold('Ответ от администратора:')}"
        )
        await message.copy_to(chat_id=user_id_to_reply)

        await message.reply("✅ Ваш ответ успешно отправлен пользователю.")

        # Очищаем данные из FSM, чтобы они не хранились вечно
        await state.storage.set_data(
            key=(admin_id_str, message_id_str),
            data={}
        )
        logger.info(f"Очищен ключ {(admin_id_str, message_id_str)} из FSM после ответа.")

    except Exception as e:
        logger.error(f"Не удалось отправить ответ от админа пользователю {user_id_to_reply}: {e}")
        await message.reply(f"❌ Не удалось отправить ответ. Ошибка: {e}")