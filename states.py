# states.py
from aiogram.fsm.state import StatesGroup, State

class NoteCreationStates(StatesGroup):
    """Состояния для процесса создания заметки."""
    awaiting_confirmation = State()

class NoteNavigationStates(StatesGroup):
    """Состояния для навигации по списку заметок."""
    browsing_notes = State()

class NoteEditingStates(StatesGroup):
    """Состояния для процесса редактирования заметки."""
    awaiting_new_text = State()

class ProfileSettingsStates(StatesGroup):
    """Состояния для настройки профиля пользователя."""
    awaiting_timezone = State()
    awaiting_reminder_time = State()

# --- НОВАЯ ГРУППА ---
class BirthdayStates(StatesGroup):
    """Состояния для управления днями рождения."""
    awaiting_person_name = State()
    awaiting_birth_date = State()
    awaiting_import_file = State()