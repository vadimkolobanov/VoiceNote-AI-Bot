# src/web/api/schemas.py
from pydantic import BaseModel, Field

class TelegramLoginData(BaseModel):
    """
    Модель для данных, получаемых от виджета Telegram Login.
    Ключи должны быть именно такими, как их присылает Telegram.
    """
    id: int
    first_name: str
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str
    last_name: str | None = None


class Token(BaseModel):
    """Модель для ответа с токеном доступа."""
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    """Модель для отображения профиля пользователя в API."""
    telegram_id: int
    first_name: str
    username: str | None
    is_vip: bool
    level: int
    xp: int
    timezone: str