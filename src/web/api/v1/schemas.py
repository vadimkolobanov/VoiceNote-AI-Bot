"""Pydantic-схемы для /api/v1/auth/* (docs/PRODUCT_PLAN.md §5.2).

Схемы в одном файле, потому что /auth — единственный feature этого PR (M1).
По мере роста v1-слоя переедут в ``schemas/auth.py`` etc.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --- User ------------------------------------------------------------------


class UserPublic(BaseModel):
    """Публичное представление пользователя (безопасно отдавать клиенту)."""

    id: int
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    timezone: str
    locale: str
    digest_hour: Optional[int] = None
    is_pro: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Auth: requests --------------------------------------------------------


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=128)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    refresh: str = Field(min_length=1, max_length=512)


# --- Auth: responses -------------------------------------------------------


class TokenPairResponse(BaseModel):
    """Единый формат для register/login/refresh (§5.2)."""

    access: str
    refresh: str
    user: UserPublic


class TokenRefreshResponse(BaseModel):
    """/auth/refresh возвращает только пару токенов без юзера (§5.2)."""

    access: str
    refresh: str
