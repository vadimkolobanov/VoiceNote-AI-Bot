# src/bot/modules/birthdays/handlers.py
import logging
import re
from datetime import datetime

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter  # <-- ИМПОРТИРУЕМ StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hitalic, hcode

from ....database import birthday_repo, user_repo
from ....core import config
from ....services.gamification_service import XP_REWARDS, check_and_grant_achievements
from ...common_utils.callbacks import BirthdayAction, PageNavigation
from ...common_utils.states import BirthdayStates
from .keyboards import get_full_birthdays_keyboard

logger = logging.getLogger(__name__)
router = Router()


# ... (весь код до хендлера отмены остается без изменений) ...
def parse_date(date_str: str) -> tuple[int, int, int | None] | None:
    """Парсит дату из строки. Возвращает (день, месяц, год) или None."""
    date_str = date_str.strip()
    # Пробуем формат ДД.ММ.ГГГГ
    match_full = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", date_str)
    if match_full:
        day, month, year = map(int, match_full.groups())
        try:
            datetime(year, month, day)
            return day, month, year
        except ValueError:
            return None

    # Пробуем формат ДД.ММ
    match_short = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})", date_str)
    if match_short:
        day, month = map(int, match_short.groups())
        try:
            # Валидируем дату на високосном году, чтобы 29.02 прошло
            datetime(2000, month, day)
            return day, month, None
        except ValueError:
            return None

    return None


async def show_birthdays_list(event: types.Message | types.CallbackQuery, state: FSMContext, page: int = 1):
    """Основная функция для отображения списка дней рождений."""
    await state.clear()

    user_id = event.from_user.id
    message = event.message if isinstance(event, types.CallbackQuery) else event

    user_profile = await user_repo.get_user_profile(user_id)
    is_vip = user_profile.get('is_vip', False)

    birthdays, total_count = await birthday_repo.get_birthdays_for_user(user_id, page=page, per_page=5)
    total_pages = (total_count + 4) // 5
    if total_pages == 0: total_pages = 1

    if total_count == 0:
        text = f"{hbold('🎂 Дни рождения')}\n\nУ вас пока нет сохраненных дат. Давайте добавим первую!"
    else:
        limit_str = "Безлимитно" if is_vip else f"{config.MAX_NOTES_MVP}"
        text = f"{hbold('🎂 Ваши сохраненные дни рождения')} ({total_count}/{limit_str})"

    keyboard = get_full_birthdays_keyboard(birthdays, page, total_pages, is_vip, total_count)

    try:
        if isinstance(event, CallbackQuery):
            await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать список дней рождений, отправляю новое сообщение: {e}")
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    if isinstance(event, CallbackQuery):
        await event.answer()


# --- Хендлеры ---

@router.callback_query(PageNavigation.filter(F.target == "birthdays"))
async def birthdays_list_handler(callback: CallbackQuery, callback_data: PageNavigation, state: FSMContext):
    """Навигация по страницам списка."""
    await show_birthdays_list(callback, state, page=callback_data.page)


@router.callback_query(BirthdayAction.filter(F.action == "add_manual"))
async def add_birthday_manual_start(callback: CallbackQuery, state: FSMContext):
    """Начинает сценарий ручного добавления дня рождения."""
    await state.set_state(BirthdayStates.awaiting_person_name)
    await callback.message.edit_text(
        "Введите имя человека (например, <b>Мама</b> или <b>Иван Петров</b>).\n\nДля отмены введите /cancel.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(BirthdayStates.awaiting_person_name, F.text, ~F.text.startswith('/'))
async def process_person_name(message: types.Message, state: FSMContext):
    """Обрабатывает введенное имя и запрашивает дату."""
    await state.update_data(person_name=message.text)
    await state.set_state(BirthdayStates.awaiting_birth_date)
    await message.answer(
        f"Отлично! Теперь введите дату рождения для {hbold(message.text)}.\n\n"
        "Используйте формат <code>ДД.ММ.ГГГГ</code> (например, <code>25.12.1980</code>) или <code>ДД.ММ</code>, если год не важен.",
        parse_mode="HTML"
    )


@router.message(BirthdayStates.awaiting_birth_date, F.text, ~F.text.startswith('/'))
async def process_birth_date(message: types.Message, state: FSMContext):
    """Обрабатывает введенную дату и сохраняет запись."""
    parsed_date = parse_date(message.text)
    if not parsed_date:
        await message.reply(
            "❌ Неверный формат даты. Пожалуйста, введите дату в формате <code>ДД.ММ.ГГГГ</code> или <code>ДД.ММ</code>.",
            parse_mode="HTML")
        return

    day, month, year = parsed_date
    user_data = await state.get_data()
    person_name = user_data.get("person_name")

    bday_record = await birthday_repo.add_birthday(message.from_user.id, person_name, day, month, year)
    if bday_record:
        await user_repo.log_user_action(message.from_user.id, 'add_birthday_manual',
                                        metadata={'birthday_id': bday_record['id']})
        await user_repo.add_xp_and_check_level_up(message.bot, message.from_user.id, XP_REWARDS['add_birthday_manual'])
        await check_and_grant_achievements(message.bot, message.from_user.id)
        await message.answer(f"✅ Готово! Напоминание о дне рождения для {hbold(person_name)} успешно добавлено.",
                             parse_mode="HTML")
    else:
        await message.answer("❌ Произошла ошибка при сохранении. Попробуйте снова.")

    await show_birthdays_list(message, state)


@router.callback_query(BirthdayAction.filter(F.action == "delete"))
async def delete_birthday_handler(callback: CallbackQuery, callback_data: BirthdayAction, state: FSMContext):
    """Удаляет запись о дне рождения."""
    success = await birthday_repo.delete_birthday(callback_data.birthday_id, callback.from_user.id)
    if success:
        await callback.answer("🗑️ Запись удалена.", show_alert=False)
    else:
        await callback.answer("❌ Ошибка при удалении.", show_alert=True)
    await show_birthdays_list(callback, state, page=callback_data.page)


@router.callback_query(BirthdayAction.filter(F.action == "import_file"))
async def import_file_start(callback: CallbackQuery, state: FSMContext):
    """Начинает сценарий импорта из файла."""
    await state.set_state(BirthdayStates.awaiting_import_file)
    text = (
        f"Пришлите мне текстовый файл (`.txt`) со списком дней рождения.\n\n"
        f"{hbold('Формат:')} каждая запись на новой строке:\n"
        f"<code>Имя - ДД.ММ.ГГГГ</code>\n\n"
        f"{hbold('Пример:')}\n"
        f"<code>Мама - 28.05.1976\n"
        f"Иван Петров - 13.06.1977\n"
        f"Годовщина - 05.09</code>\n\n"
        f"Для отмены отправьте /cancel."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(BirthdayStates.awaiting_import_file, F.document)
async def process_import_file(message: types.Message, state: FSMContext):
    """Обрабатывает загруженный .txt файл."""
    if not message.document or message.document.mime_type != "text/plain":
        await message.reply("Пожалуйста, отправьте текстовый файл с расширением .txt")
        return

    status_msg = await message.reply("⏳ Получил файл. Начинаю обработку...")
    file_info = await message.bot.get_file(message.document.file_id)

    try:
        file_content_bytes = await message.bot.download_file(file_info.file_path)
        file_content = file_content_bytes.read().decode('utf-8')
    except Exception as e:
        logger.error(f"Ошибка чтения файла для импорта дней рождений: {e}")
        await status_msg.edit_text("❌ Не удалось прочитать файл. Убедитесь, что он в кодировке UTF-8.")
        return

    lines = file_content.splitlines()
    birthdays_to_add = []
    errors = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or '-' not in line:
            if line: errors.append(f"Строка {i}: неверный формат")
            continue

        parts = line.split('-', 1)
        name = parts[0].strip()
        date_str = parts[1].strip()

        parsed_date = parse_date(date_str)
        if name and parsed_date:
            day, month, year = parsed_date
            birthdays_to_add.append((name, day, month, year))
        else:
            errors.append(f"Строка {i}: неверное имя или дата")

    if not birthdays_to_add:
        await status_msg.edit_text("В файле не найдено корректных записей. Пожалуйста, проверьте формат.")
        return

    added_count = await birthday_repo.add_birthdays_bulk(message.from_user.id, birthdays_to_add)
    if added_count > 0:
        await user_repo.log_user_action(message.from_user.id, 'import_birthdays_file',
                                        metadata={'imported_count': added_count})
        await user_repo.add_xp_and_check_level_up(message.bot, message.from_user.id, added_count * XP_REWARDS['add_birthday_manual'])
        await check_and_grant_achievements(message.bot, message.from_user.id)


    report_text = (
        f"✅ {hbold('Импорт завершен!')}\n\n"
        f"• Успешно добавлено: <b>{added_count}</b>\n"
        f"• Строк с ошибками: <b>{len(errors)}</b>"
    )
    await status_msg.edit_text(report_text, parse_mode="HTML")

    await show_birthdays_list(message, state)



@router.message(StateFilter(BirthdayStates), Command("cancel"))
async def cancel_birthday_add(message: types.Message, state: FSMContext):
    """
    Отменяет любое действие в сценариях, связанных с днями рождения.
    """
    current_state = await state.get_state()
    if current_state is None:
        return  # Если по какой-то причине состояния уже нет, ничего не делаем

    logger.info(f"Отмена состояния {current_state} для пользователя {message.from_user.id}")
    await message.answer("🚫 Действие отменено.")
    # Возвращаем пользователя к главному экрану дней рождений
    await show_birthdays_list(message, state)