# src/api/profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import time

from src.database import user_repo
from .notes import get_current_user  # Переиспользуем зависимость из notes

router = APIRouter()


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


class ProfileUpdateRequest(BaseModel):
    timezone: str | None = None
    daily_digest_enabled: bool | None = None
    daily_digest_time: time | None = None


class Achievements(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    xp_reward: int
    is_earned: bool


@router.get("/me", response_model=UserProfile, tags=["Profile"])
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserProfile, tags=["Profile"])
async def update_users_me(
        request_data: ProfileUpdateRequest,
        current_user: dict = Depends(get_current_user)
):
    user_id = current_user['telegram_id']
    # Используем model_dump(), т.к. dict() устарел
    update_data = request_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data provided to update."
        )

    # Мы будем использовать отдельные repo-функции для каждого поля
    if 'timezone' in update_data:
        await user_repo.set_user_timezone(user_id, update_data['timezone'])
    if 'daily_digest_enabled' in update_data:
        await user_repo.set_user_daily_digest_status(user_id, update_data['daily_digest_enabled'])
    if 'daily_digest_time' in update_data:
        await user_repo.set_user_daily_digest_time(user_id, update_data['daily_digest_time'])

    updated_user = await user_repo.get_user_profile(user_id)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found after update.")
    return updated_user


@router.get("/me/achievements", response_model=list[Achievements], tags=["Profile"])
async def read_my_achievements(current_user: dict = Depends(get_current_user)):
    user_id = current_user['telegram_id']
    all_achievements = await user_repo.get_all_achievements()
    user_achievements_codes = await user_repo.get_user_achievements_codes(user_id)

    result = []
    for ach in all_achievements:
        result.append({
            "code": ach['code'],
            "name": ach['name'],
            "description": ach['description'],
            "icon": ach['icon'],
            "xp_reward": ach['xp_reward'],
            "is_earned": ach['code'] in user_achievements_codes
        })
    return result