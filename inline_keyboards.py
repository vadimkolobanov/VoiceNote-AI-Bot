# inline_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from config import NOTE_CATEGORIES
from services.tz_utils import COMMON_TIMEZONES


# --- CallbackData Factories ---

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


class SettingsAction(CallbackData, prefix="settings_act"):
    action: str
    value: str | None = None


class TimezoneAction(CallbackData, prefix="tz_act"):
    action: str
    tz_name: str | None = None


class AdminAction(CallbackData, prefix="adm_act"):
    action: str
    target_user_id: int
    current_vip_status: int = 0


class AdminUserNav(CallbackData, prefix="adm_usr_nav"):
    page: int

class InfoAction(CallbackData, prefix="info_act"):
    action: str

# --- Keyboard Generators ---

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Мои заметки", callback_data=PageNavigation(target="notes", page=1, archived=False).pack())
    builder.button(text="🗄️ Архив", callback_data=PageNavigation(target="notes", page=1, archived=True).pack())
    builder.button(text="👤 Профиль", callback_data="user_profile")
    # --- НОВАЯ КНОПКА ---
    builder.button(text="ℹ️ Инфо & Помощь", callback_data=InfoAction(action="main").pack())
    builder.adjust(2, 2)  # Обновляем раскладку
    return builder.as_markup()


# --- НОВАЯ КЛАВИАТУРА ---
def get_info_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для информационного раздела."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❓ Как пользоваться", callback_data=InfoAction(action="how_to_use").pack())
    builder.button(text="⭐ VIP-возможности", callback_data=InfoAction(action="vip_features").pack())

    # Добавляем кнопки, только если ссылки есть в конфиге
    if config.NEWS_CHANNEL_URL:
        builder.button(text="📢 Новости бота", url=config.NEWS_CHANNEL_URL)
    if config.CHAT_URL:
        builder.button(text="💬 Чат для обсуждений", url=config.CHAT_URL)

    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")  # Колбэк для возврата в главное меню
    builder.adjust(2, 2, 1) if config.NEWS_CHANNEL_URL and config.CHAT_URL else builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_settings_menu_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура раздела 'Настройки'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🕒 Часовой пояс", callback_data=SettingsAction(action="go_to_timezone").pack())
    builder.button(text="⏰ Время напоминаний", callback_data=SettingsAction(action="go_to_reminders").pack())
    builder.button(text="🔔 Пред-напоминания", callback_data=SettingsAction(action="go_to_pre_reminders").pack())
    builder.button(text="⬅️ Назад в профиль", callback_data="user_profile")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


# --- НОВАЯ КЛАВИАТУРА ---
def get_request_vip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с предложением получить VIP."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Отправить заявку на VIP", callback_data=SettingsAction(action="request_vip").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(1)
    return builder.as_markup()


def get_pre_reminder_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора времени предварительного напоминания."""
    builder = InlineKeyboardBuilder()
    options = {
        "Не напоминать": 0,
        "За 30 минут": 30,
        "За 1 час": 60,
        "За 3 часа": 180,
        "За 24 часа": 1440,
    }
    for text, minutes in options.items():
        builder.button(text=text, callback_data=SettingsAction(action="set_pre_rem", value=str(minutes)).pack())

    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_reminder_time_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора времени напоминаний по умолчанию."""
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


def get_profile_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.button(text="🏠 Главное меню", callback_data="main_menu_from_notes")
    builder.adjust(1)
    return builder.as_markup()


def get_category_selection_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in NOTE_CATEGORIES:
        builder.button(
            text=category,
            callback_data=NoteAction(
                action="set_category",
                note_id=note_id,
                page=page,
                target_list=target_list,
                category=category
            ).pack()
        )
    builder.button(
        text="⬅️ Отмена",
        callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack()
    )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_note_view_actions_keyboard(note_id: int, current_page: int, is_archived: bool, is_completed: bool,
                                   has_audio: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
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
        builder.button(text="🗄️ В архив",
                       callback_data=NoteAction(action="archive", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
    else:
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
        layout = [2, 1, 1]
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
        builder.button(text="✅ Выполнено",
                       callback_data=NoteAction(action="complete", note_id=note_id, page=1).pack())
        builder.button(text="Отложить на 1 час",
                       callback_data=NoteAction(action="snooze", note_id=note_id, snooze_minutes=60).pack())
        builder.button(text="Отложить на 3 часа",
                       callback_data=NoteAction(action="snooze", note_id=note_id, snooze_minutes=180).pack())

    builder.button(
        text="👀 Просмотреть заметку",
        callback_data=NoteAction(action="view", note_id=note_id, page=1, target_list='active').pack()
    )

    if not is_pre_reminder:
        builder.adjust(1, 2, 1)
    else:
        builder.adjust(1)

    return builder.as_markup()


def get_admin_user_panel_keyboard(target_user_id: int, is_vip: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_vip_text = "❌ Забрать VIP" if is_vip else "✅ Выдать VIP"
    builder.button(
        text=toggle_vip_text,
        callback_data=AdminAction(action="toggle_vip", target_user_id=target_user_id,
                                  current_vip_status=int(is_vip)).pack()
    )
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


def get_note_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data="confirm_save_note")
    builder.button(text="❌ Отмена", callback_data="cancel_save_note")
    builder.adjust(2)
    return builder.as_markup()


def get_notes_list_display_keyboard(
        notes: list[dict], current_page: int, total_pages: int, is_archive_list: bool
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    target_list_str = 'archive' if is_archive_list else 'active'
    if not notes and current_page == 1:
        pass
    else:
        for note in notes:
            status_icon = "✅" if note.get('is_completed') else "📝"
            preview_text = f"{status_icon} #{note['note_id']} - {note['corrected_text'][:35]}"
            if len(note['corrected_text']) > 35: preview_text += "..."
            builder.button(
                text=preview_text,
                callback_data=NoteAction(action="view", note_id=note['note_id'], page=current_page,
                                         target_list=target_list_str).pack()
            )

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

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_from_notes"))
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