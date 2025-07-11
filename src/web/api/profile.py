# src/web/api/profile.py
from fastapi import APIRouter, Depends

from src.database import user_repo
from .dependencies import get_current_user
from .schemas import UserProfile

router = APIRouter()


@router.get("/me", response_model=UserProfile, tags=["Profile"])
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Возвращает профиль текущего аутентифицированного пользователя.
    """
    # Мы уже получили user dict из get_current_user, просто возвращаем его.
    # Pydantic автоматически преобразует dict в модель UserProfile.
    return current_user


@router.get("/me/achievements", tags=["Profile"])
async def read_my_achievements(current_user: dict = Depends(get_current_user)):
    """
    Возвращает список всех достижений и отмечает, какие из них получены пользователем.
    """
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