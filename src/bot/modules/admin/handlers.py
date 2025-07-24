# src/bot/modules/admin/handlers.py
import asyncio
import logging
from aiogram import Router, F, types
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hbold, hcode, hitalic

from .keyboards import get_admin_users_list_keyboard, get_admin_user_panel_keyboard
from ...common_utils.callbacks import AdminUserNav, AdminAction, SettingsAction
from ...common_utils.states import AdminStates
from ....core.config import ADMIN_TELEGRAM_ID, NEWS_CHANNEL_URL, DONATION_URL
from ....database import user_repo
from ....services.scheduler import scheduler, send_birthday_reminders, generate_and_send_daily_digest
from ....services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)
router = Router()


class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if not ADMIN_TELEGRAM_ID:
            return False
        return event.from_user.id == ADMIN_TELEGRAM_ID


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def get_broadcast_footer_keyboard() -> InlineKeyboardMarkup | None:
    """
    Создает клавиатуру-подвал для broadcast-сообщений.
    """
    builder = InlineKeyboardBuilder()
    if NEWS_CHANNEL_URL:
        builder.button(text="📢 Новости проекта", url=NEWS_CHANNEL_URL)
    if DONATION_URL:
        builder.button(text="❤️ Поддержать автора", callback_data="show_donate_info")

    if not builder.buttons:
        return None

    builder.adjust(1)
    return builder.as_markup()


async def _get_user_info_text_and_keyboard(target_user_id: int):
    """Вспомогательная функция для получения текста и клавиатуры для админ-панели."""
    user_profile = await user_repo.get_user_profile(target_user_id)
    if not user_profile:
        return None, None

    user_timezone = user_profile.get('timezone', 'UTC')
    reg_date_local_str = format_datetime_for_user(user_profile['created_at'], user_timezone)
    is_vip = user_profile.get('is_vip', False)
    vip_status_text = "✅ Да" if is_vip else "❌ Нет"

    info_text = [
        f"{hbold('👑 Админ-панель пользователя')}",
        f"▪️ {hbold('ID')}: {hcode(target_user_id)}",
        f"▪️ {hbold('Username')}: @{user_profile.get('username', 'N/A')}",
        f"▪️ {hbold('Имя')}: {user_profile.get('first_name', 'N/A')}",
        f"▪️ {hbold('VIP-статус')}: {vip_status_text}",
        f"▪️ {hbold('Часовой пояс')}: {hcode(user_timezone)}",
        f"▪️ {hbold('Зарегистрирован')}: {hitalic(reg_date_local_str)}",
        f"▪️ {hbold('Распознаваний сегодня')}: {user_profile.get('daily_stt_recognitions_count', 0)}"
    ]

    keyboard = get_admin_user_panel_keyboard(target_user_id, is_vip)

    return "\n".join(info_text), keyboard


async def _display_users_list_page(message: Message, page: int = 1):
    """Отображает страницу со списком пользователей в админ-панели."""
    users_per_page = 5
    users, total_users = await user_repo.get_all_users_paginated(page=page, per_page=users_per_page)

    total_pages = (total_users + users_per_page - 1) // users_per_page
    if total_pages == 0: total_pages = 1

    text = f"👥 {hbold('Список пользователей')} (Стр. {page}/{total_pages}, Всего: {total_users})"
    keyboard = get_admin_users_list_keyboard(users, page, total_pages)

    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Отображает информацию о пользователе и кнопки управления."""
    try:
        target_user_id_str = message.text.split()[1]
        target_user_id = int(target_user_id_str)
    except (IndexError, ValueError):
        if message.reply_to_message:
            target_user_id = message.reply_to_message.from_user.id
        else:
            await message.reply(
                "Неверный формат. Используйте:\n"
                "1. `/admin <ID>`\n"
                "2. Ответьте на сообщение пользователя командой `/admin`\n"
                "3. Используйте `/users` для просмотра списка."
            )
            return

    text, keyboard = await _get_user_info_text_and_keyboard(target_user_id)
    if not text:
        await message.reply(f"Пользователь с ID `{target_user_id}` не найден в базе данных.")
        return
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("users"))
async def cmd_users_list(message: Message):
    """Показывает первую страницу списка пользователей."""
    await _display_users_list_page(message, page=1)


@router.callback_query(AdminUserNav.filter())
async def navigate_users_list_handler(callback: CallbackQuery, callback_data: AdminUserNav):
    """Обрабатывает пагинацию по списку пользователей."""
    await _display_users_list_page(callback.message, page=callback_data.page)
    await callback.answer()


@router.callback_query(AdminAction.filter(F.action == 'show_info'))
async def show_user_info_handler(callback: CallbackQuery, callback_data: AdminAction):
    """Показывает админ-панель для выбранного пользователя из списка."""
    target_user_id = callback_data.target_user_id
    text, keyboard = await _get_user_info_text_and_keyboard(target_user_id)
    if not text:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(AdminAction.filter(F.action == 'toggle_vip'))
async def toggle_vip_status_handler(callback: CallbackQuery, callback_data: AdminAction):
    """Переключает VIP-статус и уведомляет пользователя."""
    target_user_id = callback_data.target_user_id
    new_vip_status = not bool(callback_data.current_vip_status)

    success = await user_repo.set_user_vip_status(target_user_id, new_vip_status)
    if not success:
        await callback.answer("❌ Ошибка при обновлении статуса.", show_alert=True)
        return

    try:
        if new_vip_status:
            user_notification_text = (
                f"🎉 {hbold('Поздравляем! Вам присвоен статус 👑 VIP!')} 🎉\n\n"
                "Теперь вам доступны все эксклюзивные возможности бота:\n\n"
                f"☀️ {hbold('Утренние сводки')} — получайте план на день каждое утро.\n"
                f"🔔 {hbold('Предварительные напоминания')} — бот напомнит о задаче заранее.\n"
                f"🔁 {hbold('Повторяющиеся задачи')} — для регулярных дел.\n"
                f"📥 {hbold('Импорт дней рождения')} — загружайте все важные даты из файла.\n"
                f"♾️ {hbold('Безлимитные заметки')} и распознавания голоса.\n\n"
                "Все эти функции можно настроить под себя в разделе 'Профиль' -> '⚙️ Настройки'."
            )
            kb = types.InlineKeyboardMarkup(inline_keyboard=[[
                types.InlineKeyboardButton(
                    text="🚀 Перейти к настройкам",
                    callback_data=SettingsAction(action="go_to_main").pack()
                )
            ]])
            await callback.bot.send_message(target_user_id, user_notification_text, parse_mode="HTML", reply_markup=kb)
        else:
            await user_repo.reset_user_vip_settings(target_user_id)
            user_notification_text = f"ℹ️ {hbold('Изменение статуса')}\n\nВаш VIP-статус был изменен администратором. Теперь для вашего аккаунта действуют стандартные лимиты."
            await callback.bot.send_message(target_user_id, user_notification_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о смене VIP-статуса пользователю {target_user_id}: {e}")

    status_text = "выдан" if new_vip_status else "забран"
    await callback.answer(f"✅ VIP-статус {status_text}! Пользователь уведомлен.", show_alert=False)

    logger.info(f"Администратор {callback.from_user.id} изменил VIP-статус для {target_user_id} на {new_vip_status}")

    new_text, new_keyboard = await _get_user_info_text_and_keyboard(target_user_id)
    if new_text:
        try:
            await callback.message.edit_text(new_text, reply_markup=new_keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось обновить админ-панель: {e}")


@router.message(Command("broadcast"))
async def cmd_broadcast_start(message: Message, state: FSMContext):
    """Начинает сценарий массовой рассылки."""
    await state.set_state(AdminStates.awaiting_broadcast_message)
    await message.answer(
        "Введите сообщение для рассылки всем пользователям.\n"
        "Поддерживается форматирование, фото, стикеры и т.д.\n\n"
        "Для отмены введите /cancel"
    )


@router.message(AdminStates.awaiting_broadcast_message, Command("cancel"))
async def cmd_broadcast_cancel(message: Message, state: FSMContext):
    """Отменяет процесс рассылки."""
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(AdminStates.awaiting_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Запускает процесс рассылки сообщения всем пользователям."""
    await state.clear()
    all_users, _ = await user_repo.get_all_users_paginated(page=1, per_page=1_000_000)
    user_ids = [user['telegram_id'] for user in all_users]

    if not user_ids:
        await message.answer("В базе данных нет пользователей для рассылки.")
        return

    asyncio.create_task(broadcast_to_users(message, user_ids))

    await message.answer(f"✅ Рассылка запущена для {len(user_ids)} пользователей.")


async def broadcast_to_users(source_message: Message, user_ids: list[int]):
    """
    Асинхронная функция для отправки сообщения пользователям с учетом лимитов Telegram.
    """
    total_users = len(user_ids)
    sent_count = 0
    failed_count = 0

    keyboard = get_broadcast_footer_keyboard()

    status_message = await source_message.bot.send_message(
        chat_id=source_message.from_user.id,
        text=f"⏳ Рассылка началась... (0/{total_users})"
    )

    for i, user_id in enumerate(user_ids):
        try:
            await source_message.copy_to(chat_id=user_id, reply_markup=keyboard)
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.warning(f"Рассылка: не удалось отправить сообщение пользователю {user_id}. Ошибка: {e}")

        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)
            try:
                await status_message.edit_text(f"⏳ В процессе... ({i + 1}/{total_users})")
            except Exception:
                pass

    final_report = (
        f"🏁 Рассылка завершена!\n\n"
        f"✅ Успешно отправлено: {sent_count}\n"
        f"❌ Не удалось отправить: {failed_count}\n"
        f"👥 Всего пользователей: {total_users}"
    )
    await status_message.edit_text(final_report)


@router.message(Command("jobs"))
async def cmd_show_jobs(message: Message):
    """Показывает все активные задачи в планировщике APScheduler."""
    jobs = scheduler.get_jobs()
    if not jobs:
        await message.answer("В планировщике нет активных задач.")
        return

    response_lines = [f"{hbold('Активные задачи в планировщике:')}\n"]
    for job in jobs:
        run_date_local = job.next_run_time.astimezone(None)
        job_info = (
            f"▪️ {hbold('ID:')} {hcode(job.id)}\n"
            f"  - {hbold('Сработает:')} {hitalic(run_date_local.strftime('%Y-%m-%d %H:%M:%S'))}\n"
            f"  - {hbold('Функция:')} {hcode(job.func.__name__)}"
        )
        response_lines.append(job_info)
    await message.answer("\n\n".join(response_lines), parse_mode="HTML")


@router.message(Command("test_bday"))
async def cmd_test_birthday_check(message: Message):
    """Принудительно запускает проверку дней рождений."""
    await message.answer("⏳ Принудительно запускаю проверку дней рождений...")
    await send_birthday_reminders(message.bot)
    await message.answer("✅ Проверка завершена. Смотрите логи и личные сообщения пользователей.")


@router.message(Command("test_digest"))
async def cmd_test_digest(message: Message):
    """Принудительно запускает генерацию утренней сводки для себя."""
    await message.answer("⏳ Готовлю утреннюю сводку для вас...")
    user_profile = await user_repo.get_user_profile(message.from_user.id)
    if not user_profile or not user_profile.get('is_vip'):
        await message.answer("❌ Эта команда только для VIP-пользователей.")
        return
    await generate_and_send_daily_digest(message.bot, user_profile)
    await message.answer("✅ Задача выполнена. Проверьте личные сообщения.")