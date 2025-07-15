# src/web/api/schemas.py
from pydantic import BaseModel, Field
from datetime import datetime, time

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
    default_reminder_time: time
    pre_reminder_minutes: int
    daily_digest_enabled: bool
    daily_digest_time: time

    class Config:
        from_attributes = True

class Note(BaseModel):
    note_id: int
    owner_id: int
    summary_text: str | None
    corrected_text: str
    category: str | None
    created_at: datetime
    updated_at: datetime
    note_taken_at: datetime | None
    due_date: datetime | None
    recurrence_rule: str | None
    is_archived: bool
    is_completed: bool
    llm_analysis_json: dict | None = None

    class Config:
        from_attributes = True

class PaginatedNotesResponse(BaseModel):
    items: list[Note]
    total: int
    page: int
    per_page: int
    total_pages: int

class NoteCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Текст для создания новой заметки")

class NoteUpdateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Новый полный текст заметки")

class Birthday(BaseModel):
    id: int
    person_name: str
    birth_day: int
    birth_month: int
    birth_year: int | None

    class Config:
        from_attributes = True

class BirthdayCreateRequest(BaseModel):
    person_name: str = Field(..., min_length=1)
    birth_date: str = Field(..., description="Дата в формате DD.MM.YYYY или DD.MM")

class PaginatedBirthdaysResponse(BaseModel):
    items: list[Birthday]
    total: int
    page: int
    per_page: int
    total_pages: int

class ProfileUpdateRequest(BaseModel):
    timezone: str | None = None
    default_reminder_time: time | None = None
    pre_reminder_minutes: int | None = None
    daily_digest_enabled: bool | None = None
    daily_digest_time: time | None = None

class ShoppingListItem(BaseModel):
    item_name: str
    checked: bool
    added_by: int | None = None

class Participant(BaseModel):
    telegram_id: int
    first_name: str

class ShoppingListNote(Note):
    llm_analysis_json: dict[str, list[ShoppingListItem]] | None = Field(default_factory=dict)
    participants: list[Participant] = []

class ShoppingListItemUpdate(BaseModel):
    item_index: int
    checked: bool

class DeviceTokenRegister(BaseModel):
    fcm_token: str
    platform: str = "android"