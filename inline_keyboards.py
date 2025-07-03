# inline_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from config import NOTE_CATEGORIES, MAX_NOTES_MVP
from services.tz_utils import COMMON_TIMEZONES


class NoteAction(CallbackData, prefix="note_act"):
    action: str
    note_id: int
    page: int = 1
    target_list: str = 'active'
    category: str | None = None
    snooze_minutes: int | None = None


class PageNavigation(CallbackData, prefix="pg_nav"):
    target: str
    page: int
    archived: bool = False
    user_id: int | None = None


class SettingsAction(CallbackData, prefix="settings_act"):
    action: str
    value: str | None = None


class TimezoneAction(CallbackData, prefix="tz_act"):
    action: str
    tz_name: str | None = None


class InfoAction(CallbackData, prefix="info_act"):
    action: str


class BirthdayAction(CallbackData, prefix="bday_act"):
    action: str
    birthday_id: int | None = None
    page: int = 1


class AdminAction(CallbackData, prefix="adm_act"):
    action: str
    target_user_id: int
    current_vip_status: int = 0


class AdminUserNav(CallbackData, prefix="adm_usr_nav"):
    page: int


def get_main_menu_keyboard(is_vip: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not is_vip:
        builder.button(
            text="🚀 Получить VIP бесплатно",
            callback_data=SettingsAction(action="get_free_vip").pack()
        )

    builder.button(text="📝 Мои заметки", callback_data=PageNavigation(target="notes", page=1, archived=False).pack())
    builder.button(text="🗄️ Архив", callback_data=PageNavigation(target="notes", page=1, archived=True).pack())
    builder.button(text="👤 Профиль", callback_data="user_profile")
    builder.button(text="⚙️ Настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.button(text="ℹ️ Инфо", callback_data=InfoAction(action="main").pack())

    if config.DONATION_URL:
        builder.button(text="❤️ Поддержка", callback_data="show_donate_info")

    builder.button(text="💬 Сообщить о проблеме", callback_data="report_problem")

    if not is_vip:
        builder.adjust(1, 2, 2, 2, 1)
    else:
        builder.adjust(2, 2, 2, 1)

    return builder.as_markup()


def get_profile_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎂 Дни рождения", callback_data=PageNavigation(target="birthdays", page=1).pack())
    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_info_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❓ Как пользоваться", callback_data=InfoAction(action="how_to_use").pack())
    builder.button(text="⭐ VIP-возможности", callback_data=InfoAction(action="vip_features").pack())
    if config.NEWS_CHANNEL_URL:
        builder.button(text="📢 Новости бота", url=config.NEWS_CHANNEL_URL)
    if config.CHAT_URL:
        builder.button(text="💬 Чат для обсуждений", url=config.CHAT_URL)

    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")

    layout = [2]
    if config.NEWS_CHANNEL_URL and config.CHAT_URL:
        layout.append(2)
    elif config.NEWS_CHANNEL_URL or config.CHAT_URL:
        layout.append(1)
    layout.append(1)
    builder.adjust(*layout)
    return builder.as_markup()


def get_settings_menu_keyboard(
        daily_digest_enabled: bool = True,
        is_alice_linked: bool = False
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🕒 Часовой пояс", callback_data=SettingsAction(action="go_to_timezone").pack())
    digest_btn_text = "끄 Выключить утреннюю сводку" if daily_digest_enabled else " включить утреннюю сводку"
    builder.button(text=digest_btn_text, callback_data=SettingsAction(action="toggle_digest").pack())
    builder.button(text="⏰ Время напоминаний (⭐VIP)", callback_data=SettingsAction(action="go_to_reminders").pack())
    builder.button(text="🔔 Пред-напоминания (⭐VIP)", callback_data=SettingsAction(action="go_to_pre_reminders").pack())

    if not is_alice_linked:
        builder.button(text="🔗 Привязать Яндекс.Алису", callback_data=SettingsAction(action="link_alice").pack())

    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")

    layout = [1, 1, 2]
    if not is_alice_linked:
        layout.append(1)
    layout.append(1)
    builder.adjust(*layout)

    return builder.as_markup()


def get_request_vip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Отправить заявку на VIP", callback_data=SettingsAction(action="request_vip").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(1)
    return builder.as_markup()


def get_pre_reminder_keyboard() -> InlineKeyboardMarkup:
    options = {"Не напоминать": 0, "За 30 минут": 30, "За 1 час": 60, "За 3 часа": 180, "За 24 часа": 1440}
    builder = InlineKeyboardBuilder()
    for text, minutes in options.items():
        builder.button(text=text, callback_data=SettingsAction(action="set_pre_rem", value=str(minutes)).pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_reminder_time_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    times = ["09:00", "10:00", "12:00", "18:00", "20:00", "21:00"]
    for t in times:
        safe_time_value = t.replace(':', '-')
        builder.button(text=t, callback_data=SettingsAction(action="set_rem_time", value=safe_time_value).pack())
    builder.button(text="⌨️ Ввести вручную", callback_data=SettingsAction(action="manual_rem_time").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()


def get_timezone_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for display_name, iana_name in COMMON_TIMEZONES.items():
        builder.button(text=display_name, callback_data=TimezoneAction(action="set", tz_name=iana_name).pack())
    builder.button(text="⌨️ Ввести вручную", callback_data=TimezoneAction(action="manual_input").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(2, 2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def get_category_selection_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in NOTE_CATEGORIES:
        builder.button(text=category, callback_data=NoteAction(action="set_category", note_id=note_id, page=page,
                                                               target_list=target_list, category=category).pack())
    builder.button(text="⬅️ Отмена",
                   callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack())
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_note_view_actions_keyboard(note: dict, current_page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    note_id = note['note_id']
    is_archived = note.get('is_archived', False)
    is_completed = note.get('is_completed', False)
    has_audio = bool(note.get('original_audio_telegram_file_id'))
    is_recurring = bool(note.get('recurrence_rule'))
    is_vip = note.get('is_vip', False)
    target_list_str = 'archive' if is_archived else 'active'

    if is_completed:
        builder.button(text="🗑️ Удалить навсегда",
                       callback_data=NoteAction(action="confirm_delete", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
    elif not is_archived:
        builder.button(text="✅ Выполнено",
                       callback_data=NoteAction(action="complete", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
        builder.button(text="✏️ Редактировать",
                       callback_data=NoteAction(action="edit", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
        builder.button(text="🗂️ Изменить категорию",
                       callback_data=NoteAction(action="change_category", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
        if is_recurring and is_vip:
            builder.button(text="⭐ 🔁 Сделать разовой",
                           callback_data=NoteAction(action="stop_recurrence", note_id=note_id, page=current_page,
                                                    target_list=target_list_str).pack())
        builder.button(text="🗄️ В архив", callback_data=NoteAction(action="archive", note_id=note_id, page=current_page,
                                                                   target_list=target_list_str).pack())
    else:  # is_archived
        builder.button(text="↩️ Восстановить",
                       callback_data=NoteAction(action="unarchive", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
        builder.button(text="🗑️ Удалить навсегда",
                       callback_data=NoteAction(action="confirm_delete", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
    if has_audio and not is_completed:
        builder.button(text="🎧 Прослушать оригинал",
                       callback_data=NoteAction(action="listen_audio", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())

    list_button_text = "⬅️ К архиву" if is_archived else "⬅️ К списку заметок"
    builder.button(text=list_button_text,
                   callback_data=PageNavigation(target="notes", page=current_page, archived=is_archived).pack())

    if is_completed:
        builder.adjust(1, 1)
    elif not is_archived:
        layout = [2, 1]
        if is_recurring and is_vip: layout.append(1)
        layout.append(1)
        if has_audio: layout.append(1)
        layout.append(1)
        builder.adjust(*layout)
    else:
        layout = [1, 1]
        if has_audio: layout.append(1)
        layout.append(1)
        builder.adjust(*layout)

    return builder.as_markup()


def get_reminder_notification_keyboard(note_id: int, is_pre_reminder: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not is_pre_reminder:
        builder.button(text="✅ Выполнено", callback_data=NoteAction(action="complete", note_id=note_id, page=1).pack())
        builder.button(text="Отложить на 1 час",
                       callback_data=NoteAction(action="snooze", note_id=note_id, snooze_minutes=60).pack())
        builder.button(text="Отложить на 3 часа",
                       callback_data=NoteAction(action="snooze", note_id=note_id, snooze_minutes=180).pack())
    builder.button(text="👀 Просмотреть заметку",
                   callback_data=NoteAction(action="view", note_id=note_id, page=1, target_list='active').pack())
    builder.adjust(1, 2, 1) if not is_pre_reminder else builder.adjust(1)
    return builder.as_markup()


def get_admin_user_panel_keyboard(target_user_id: int, is_vip: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_vip_text = "❌ Забрать VIP" if is_vip else "✅ Выдать VIP"
    builder.button(text=toggle_vip_text, callback_data=AdminAction(action="toggle_vip", target_user_id=target_user_id,
                                                                   current_vip_status=int(is_vip)).pack())
    builder.button(text="⬅️ К списку пользователей", callback_data=AdminUserNav(page=1).pack())
    builder.adjust(1)
    return builder.as_markup()


def get_admin_users_list_keyboard(users: list[dict], current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in users:
        vip_icon = "👑" if user.get('is_vip') else ""
        user_name = user.get('first_name') or f"ID: {user['telegram_id']}"
        preview_text = f"{vip_icon} {user_name} (@{user.get('username', 'N/A')})"
        builder.button(text=preview_text,
                       callback_data=AdminAction(action="show_info", target_user_id=user['telegram_id']).pack())
    builder.adjust(1)
    pagination_row = []
    if current_page > 1:
        pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=AdminUserNav(page=current_page - 1).pack()))
    if total_pages > 1:
        pagination_row.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="ignore"))
    if current_page < total_pages:
        pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=AdminUserNav(page=current_page + 1).pack()))
    if pagination_row:
        builder.row(*pagination_row)
    return builder.as_markup()


def get_note_creation_response_keyboard(note_id: int, show_tz_button: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой 'Отменить' и опционально 'Настроить ТЗ'."""
    builder = InlineKeyboardBuilder()
    if show_tz_button:
        builder.button(
            text="🕒 Установить мой часовой пояс",
            callback_data=SettingsAction(action="go_to_timezone").pack()
        )
    builder.button(
        text="❌ Отменить создание",
        callback_data=NoteAction(action="undo_create", note_id=note_id).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_notes_list_display_keyboard(notes: list[dict], current_page: int, total_pages: int,
                                    is_archive_list: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    target_list_str = 'archive' if is_archive_list else 'active'
    if not notes and current_page == 1:
        pass
    else:
        for note in notes:
            status_icon = "✅" if note.get('is_completed') else "📝"
            preview_text = f"{status_icon} #{note['note_id']} - {note['corrected_text'][:35]}"
            if len(note['corrected_text']) > 35: preview_text += "..."
            builder.button(text=preview_text,
                           callback_data=NoteAction(action="view", note_id=note['note_id'], page=current_page,
                                                    target_list=target_list_str).pack())
    builder.adjust(1)
    pagination_row_items = []
    if current_page > 1:
        pagination_row_items.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=PageNavigation(target="notes",
                                                                                                       page=current_page - 1,
                                                                                                       archived=is_archive_list).pack()))
    if total_pages > 1:
        pagination_row_items.append(
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="ignore_page_display"))
    if current_page < total_pages:
        pagination_row_items.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=PageNavigation(target="notes",
                                                                                                        page=current_page + 1,
                                                                                                        archived=is_archive_list).pack()))
    if pagination_row_items: builder.row(*pagination_row_items)
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_main_menu"))
    return builder.as_markup()


def get_confirm_delete_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="‼️ ДА, УДАЛИТЬ НАВСЕГДА ‼️",
                   callback_data=NoteAction(action="delete", note_id=note_id, page=page,
                                            target_list=target_list).pack())
    builder.button(text="Отмена",
                   callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack())
    builder.adjust(1)
    return builder.as_markup()


def get_birthdays_menu_keyboard(is_vip: bool, current_count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_vip or current_count < config.MAX_NOTES_MVP:
        builder.button(text="➕ Добавить вручную", callback_data=BirthdayAction(action="add_manual").pack())
    else:
        builder.button(text="⭐ Увеличить лимит (VIP)", callback_data=SettingsAction(action="request_vip").pack())
    if is_vip:
        builder.button(text="📥 Импорт из файла", callback_data=BirthdayAction(action="import_file").pack())
    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_birthdays_list_keyboard(birthdays: list[dict], page: int, total_pages: int,
                                user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for bday in birthdays:
        year_str = f" ({bday['birth_year']})" if bday['birth_year'] else ""
        date_str = f"{bday['birth_day']:02}.{bday['birth_month']:02}{year_str}"
        builder.button(text=f"{bday['person_name']} - {date_str}", callback_data="ignore_bday_view")
        builder.button(text="🗑️",
                       callback_data=BirthdayAction(action="delete", birthday_id=bday['id'], page=page).pack())
    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton(text="⬅️",
                                                   callback_data=PageNavigation(target="birthdays", page=page - 1,
                                                                                user_id=user_id).pack()))
    if total_pages > 1:
        pagination_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(text="➡️",
                                                   callback_data=PageNavigation(target="birthdays", page=page + 1,
                                                                                user_id=user_id).pack()))
    builder.adjust(2)
    if pagination_row:
        builder.row(*pagination_row)
    return builder.as_markup()