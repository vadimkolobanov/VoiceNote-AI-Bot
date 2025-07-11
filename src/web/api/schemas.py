# src/web/api/schemas.py
from pydantic import BaseModel, Field
from datetime import datetime

# --- Существующие схемы ---
class TelegramLoginData(BaseModel):
    id: int
    first_name: str
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str
    last_name: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserProfile(BaseModel):
    telegram_id: int
    first_name: str
    username: str | None
    is_vip: bool
    level: int
    xp: int
    timezone: str


# --- НОВЫЕ СХЕМЫ ДЛЯ ЗАМЕТОК ---
class Note(BaseModel):
    """Модель для отображения одной заметки в API."""
    note_id: int
    summary_text: str | None
    corrected_text: str
    category: str | None
    created_at: datetime
    due_date: datetime | None
    is_completed: bool

    class Config:
        # Pydantic v2+ использует from_attributes вместо orm_mode
        from_attributes = True


class PaginatedNotesResponse(BaseModel):
    """Модель для ответа с пагинированным списком заметок."""
    items: list[Note]
    total: int
    page: int
    per_page: int
    total_pages: int