# src/bot/common_utils/callbacks.py
from aiogram.filters.callback_data import CallbackData


class NoteAction(CallbackData, prefix="note_act"):
    """
    Действия, связанные с конкретной заметкой.
    - action: 'view', 'edit', 'delete', 'complete', 'archive', etc.
    - note_id: ID заметки.
    - page: Номер страницы для возврата к списку.
    - target_list: 'active' или 'archive' для возврата к правильному списку.
    - category: Для установки новой категории.
    - snooze_minutes: Для откладывания напоминания.
    """
    action: str
    note_id: int
    page: int = 1
    target_list: str = 'active'
    category: str | None = None
    snooze_minutes: int | None = None


class ShoppingListAction(CallbackData, prefix="shop_list"):
    """Действия, связанные со списком покупок."""
    action: str
    note_id: int
    item_index: int | None = None


class ShoppingListReminder(CallbackData, prefix="shop_rem"):
    """Действия для установки напоминания о списке покупок."""
    action: str # 'show_options', 'set', 'cancel'
    note_id: int
    value: str | None = None # Используем строковое значение для гибкости


class PageNavigation(CallbackData, prefix="pg_nav"):
    """
    Пагинация для списков.
    - target: 'notes' или 'birthdays'.
    - page: Номер страницы для перехода.
    - archived: Флаг для списка заметок (активные или архив).
    """
    target: str
    page: int
    archived: bool = False


class SettingsAction(CallbackData, prefix="settings_act"):
    """Действия в меню настроек."""
    action: str
    value: str | None = None  # Для передачи значений, например, времени


class TimezoneAction(CallbackData, prefix="tz_act"):
    """Действия в меню выбора часового пояса."""
    action: str
    tz_name: str | None = None


class InfoAction(CallbackData, prefix="info_act"):
    """Действия в информационном/справочном разделе."""
    action: str # main, guides, guide_..., support
    guide_topic: str | None = None


class BirthdayAction(CallbackData, prefix="bday_act"):
    """Действия, связанные с днями рождения."""
    action: str
    birthday_id: int | None = None
    page: int = 1


class AdminAction(CallbackData, prefix="adm_act"):
    """Действия в админ-панели для управления пользователем."""
    action: str
    target_user_id: int
    current_vip_status: int = 0  # Используем int(bool) для передачи


class AdminUserNav(CallbackData, prefix="adm_usr_nav"):
    """Пагинация по списку пользователей в админ-панели."""
    page: int