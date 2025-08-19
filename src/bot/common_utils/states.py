# src/bot/common_utils/states.py
from aiogram.fsm.state import StatesGroup, State


class OnboardingStates(StatesGroup):
    """Состояния для процесса обучения нового пользователя."""
    step_1_welcome = State()
    step_2_create_note = State()
    step_3_timezone = State()
    step_4_advanced_notes = State() # Списки покупок и шаринг
    step_5_birthdays = State()      # Повторяющиеся задачи и ДР
    step_6_vip = State()
    step_7_final = State()


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
    awaiting_city_name = State()


class BirthdayStates(StatesGroup):
    """Состояния для управления днями рождения."""
    awaiting_person_name = State()
    awaiting_birth_date = State()
    awaiting_import_file = State()


class AdminStates(StatesGroup):
    """Состояния для админ-функций, таких как рассылка."""
    awaiting_broadcast_message = State()
    awaiting_direct_message = State()


class SupportStates(StatesGroup):
    """Состояния для системы поддержки."""
    awaiting_report_message = State()


class NotesSearchStates(StatesGroup):
    waiting_for_query = State()