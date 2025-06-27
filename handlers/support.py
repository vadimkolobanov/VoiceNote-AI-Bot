# handlers/support.py
import logging
import re

from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic

from config import ADMIN_TELEGRAM_ID
from handlers.admin import IsAdmin
from states import SupportStates

logger = logging.getLogger(__name__)
router = Router()


# --- Хендлеры для пользователя ---

@router.callback_query(F.data == "report_problem")
async def start_report_handler(callback: types.CallbackQuery, state: FSMContext):
    """Начинает сценарий отправки репорта."""
    await state.clear()
    await state.set_state(SupportStates.awaiting_report_message)
    await callback.message.edit_text(
        "Опишите вашу проблему или предложение одним сообщением. Вы можете прикрепить фото или видео, если это необходимо.\n\n"
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
    и уведомляет пользователя об успешной отправке.
    """
    await state.clear()  # Сбрасываем состояние сразу

    if not ADMIN_TELEGRAM_ID:
        await message.answer("К сожалению, функция отправки репортов временно недоступна.")
        return

    user = message.from_user
    info_text = (
        f"‼️ {hbold('Новый репорт о проблеме')}\n\n"
        f"От: {hitalic(user.full_name)}\n"
        f"Username: @{user.username if user.username else 'N/A'}\n"
        f"ID для ответа: `{user.id}`\n\n"
        f"Чтобы ответить, используйте функцию 'Ответить' на {hbold('пересланное')} сообщение."
    )

    try:
        await message.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=info_text,
            parse_mode="HTML"
        )
        forwarded_message = await message.forward(chat_id=ADMIN_TELEGRAM_ID)

        await state.storage.set_data(
            key=(str(ADMIN_TELEGRAM_ID), str(forwarded_message.message_id)),
            data={'user_id_to_reply': user.id}
        )
        logger.info(
            f"Сохранили в FSM ключ {(str(ADMIN_TELEGRAM_ID), str(forwarded_message.message_id))} для пользователя {user.id}")

        await message.answer("✅ Спасибо! Ваше сообщение было отправлено администратору. Мы скоро с вами свяжемся.")
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

    # Ключевое изменение: проверяем, что это пересланное сообщение, но не требуем `forward_from`
    # Вместо этого, мы будем полагаться на данные из хранилища.
    # Если это не пересланное сообщение, то это ответ на что-то другое, и мы его игнорируем.
    if replied_to_message.forward_date is None:
        logger.debug("Админ ответил не на пересланное сообщение. Игнорируем.")
        return

    admin_id_str = str(message.from_user.id)
    message_id_str = str(replied_to_message.message_id)

    logger.info(f"Админ {admin_id_str} ответил на сообщение {message_id_str}. Ищем ключ в FSM...")

    storage_data = await state.storage.get_data(
        key=(admin_id_str, message_id_str)
    )

    user_id_to_reply = storage_data.get('user_id_to_reply') if storage_data else None

    if user_id_to_reply:
        logger.info(f"Нашли ID пользователя в FSM: {user_id_to_reply}")
    else:
        # Резервный вариант для старых сообщений или если FSM очистился (например, после перезапуска)
        if replied_to_message.forward_from:
            user_id_to_reply = replied_to_message.forward_from.id
            logger.warning(f"Не нашли ID в FSM, используем резервный вариант: {user_id_to_reply}")
        else:
            logger.warning(f"Не нашли ID в FSM и нет резервного варианта. Не можем ответить.")
            await message.reply(
                "Не удалось определить получателя. Возможно, это старое сообщение или пользователь скрыл свой аккаунт.")
            return

    try:
        await bot.send_message(
            chat_id=user_id_to_reply,
            text=f"✉️ {hbold('Ответ от администратора:')}"
        )
        await message.copy_to(chat_id=user_id_to_reply)
        await message.reply("✅ Ваш ответ успешно отправлен пользователю.")

        await state.storage.set_data(
            key=(admin_id_str, message_id_str),
            data={}
        )
        logger.info(f"Очистили ключ {(admin_id_str, message_id_str)} из FSM.")

    except Exception as e:
        logger.error(f"Не удалось отправить ответ от админа пользователю {user_id_to_reply}: {e}")
        await message.reply(f"❌ Не удалось отправить ответ. Ошибка: {e}")