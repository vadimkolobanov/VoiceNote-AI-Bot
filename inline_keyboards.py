# inline_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import NOTE_CATEGORIES  # <--- НОВЫЙ ИМПОРТ
from services.tz_utils import COMMON_TIMEZONES


# --- CallbackData Factories ---

class NoteAction(CallbackData, prefix="note_act"):
    action: str
    note_id: int
    page: int = 1
    target_list: str = 'active'
    # <--- НОВОЕ ПОЛЕ для категорий --->
    category: str | None = None


# ... (остальные CallbackData без изменений) ...
class PageNavigation(CallbackData, prefix="pg_nav"):
    target: str
    page: int
    archived: bool = False


class TimezoneAction(CallbackData, prefix="tz_act"):
    action: str
    tz_name: str | None = None


class AdminAction(CallbackData, prefix="adm_act"):
    action: str
    target_user_id: int
    current_vip_status: int = 0


class AdminUserNav(CallbackData, prefix="adm_usr_nav"):
    page: int


# --- Keyboard Generators ---

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    # ... (без изменений) ...
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Мои заметки", callback_data=PageNavigation(target="notes", page=1, archived=False).pack())
    builder.button(text="🗄️ Архив", callback_data=PageNavigation(target="notes", page=1, archived=True).pack())
    builder.button(text="👤 Профиль", callback_data="user_profile")
    builder.adjust(2, 1)
    return builder.as_markup()


# ... (get_timezone_selection_keyboard, get_profile_actions_keyboard без изменений) ...
def get_timezone_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for display_name, iana_name in COMMON_TIMEZONES.items():
        builder.button(text=display_name, callback_data=TimezoneAction(action="set", tz_name=iana_name).pack())
    builder.button(text="⌨️ Ввести вручную", callback_data=TimezoneAction(action="manual_input").pack())
    builder.button(text="⬅️ Назад в профиль", callback_data="user_profile")
    builder.adjust(2, 2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def get_profile_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Настроить часовой пояс", callback_data="set_timezone")
    builder.button(text="🏠 Главное меню", callback_data="main_menu_from_notes")
    builder.adjust(1)
    return builder.as_markup()


# <--- НОВАЯ КЛАВИАТУРА --->
def get_category_selection_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    """Клавиатура для выбора новой категории для заметки."""
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

    # Кнопка отмены (возврат к просмотру заметки)
    builder.button(
        text="⬅️ Отмена",
        callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack()
    )
    builder.adjust(2)  # По 2 категории в ряд для компактности
    return builder.as_markup()


def get_note_view_actions_keyboard(note_id: int, current_page: int, is_archived: bool,
                                   has_audio: bool) -> InlineKeyboardMarkup:
    # <--- Обновляем эту клавиатуру, чтобы добавить новые кнопки --->
    builder = InlineKeyboardBuilder()
    target_list_str = 'archive' if is_archived else 'active'

    # Кнопки, доступные только для активных заметок
    if not is_archived:
        builder.button(text="✏️ Редактировать",
                       callback_data=NoteAction(action="edit", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
        builder.button(text="🗂️ Изменить категорию",
                       callback_data=NoteAction(action="change_category", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())
        builder.button(text="🗄️ В архив", callback_data=NoteAction(action="archive", note_id=note_id, page=current_page,
                                                                   target_list=target_list_str).pack())
    else:  # Для архивированных
        builder.button(text="↩️ Восстановить",
                       callback_data=NoteAction(action="unarchive", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())

    # Кнопка прослушивания аудио, если оно есть
    if has_audio:
        builder.button(text="🎧 Прослушать оригинал",
                       callback_data=NoteAction(action="listen_audio", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())

    # Общие кнопки
    builder.button(text="🗑️ Удалить навсегда",
                   callback_data=NoteAction(action="confirm_delete", note_id=note_id, page=current_page,
                                            target_list=target_list_str).pack())
    list_button_text = "⬅️ К архиву" if is_archived else "⬅️ К списку заметок"
    builder.button(text=list_button_text,
                   callback_data=PageNavigation(target="notes", page=current_page, archived=is_archived).pack())

    # Адаптивная раскладка
    if not is_archived:
        builder.adjust(2, 1, 1, 1, 1) if has_audio else builder.adjust(2, 1, 1, 1)
    else:
        builder.adjust(1, 1, 1, 1) if has_audio else builder.adjust(1, 1, 1)

    return builder.as_markup()


def get_reminder_notification_keyboard(note_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="👀 Просмотреть заметку",
        callback_data=NoteAction(action="view", note_id=note_id, page=1, target_list='active').pack()
    )
    return builder.as_markup()


# ... (остальные клавиатуры без изменений) ...
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
            preview_text = f"#{note['note_id']} - {note['corrected_text'][:35]}"
            if len(note['corrected_text']) > 35: preview_text += "..."
            builder.button(
                text=preview_text,
                callback_data=NoteAction(action="view", note_id=note['note_id'], page=current_page,
                                         target_list=target_list_str).pack()
            )
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
    builder.adjust(1)
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