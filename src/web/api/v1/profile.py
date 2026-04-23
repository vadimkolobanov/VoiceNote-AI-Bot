"""/api/v1/profile — GET/PATCH (PRODUCT_PLAN.md §5.2)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.session import get_session

from .dependencies import get_current_user
from .schemas import UserPublic

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfilePatchIn(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    timezone: Optional[str] = Field(default=None, max_length=64)
    locale: Optional[str] = Field(default=None, pattern="^(ru|en)$")
    digest_hour: Optional[int] = Field(default=None, ge=0, le=23)


def _to_public(u: User) -> UserPublic:
    return UserPublic(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        timezone=u.timezone,
        locale=u.locale,
        digest_hour=u.digest_hour,
        is_pro=u.is_pro(),
        created_at=u.created_at,
    )


@router.get("", response_model=UserPublic)
async def get_profile(user: User = Depends(get_current_user)) -> UserPublic:
    return _to_public(user)


@router.patch("", response_model=UserPublic)
async def patch_profile(
    payload: ProfilePatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserPublic:
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.timezone is not None:
        user.timezone = payload.timezone
    if payload.locale is not None:
        user.locale = payload.locale
    if payload.digest_hour is not None:
        user.digest_hour = payload.digest_hour
    return _to_public(user)
