# states.py
from aiogram.fsm.state import StatesGroup, State

class NoteCreationStates(StatesGroup):
    """Состояния для процесса создания заметки."""
    awaiting_confirmation = State()

class NoteNavigationStates(StatesGroup):
    """Состояния для навигации по списку заметок."""
    browsing_notes = State()