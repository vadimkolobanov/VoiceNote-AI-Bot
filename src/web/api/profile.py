# src/web/api/profile.py
from fastapi import APIRouter, Depends, HTTPException, status

from src.database import user_repo
from .dependencies import get_current_user
from .schemas import UserProfile, ProfileUpdateRequest, DeviceTokenRegister

router = APIRouter()

@router.get("/me", response_model=UserProfile, tags=["Profile"])
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserProfile, tags=["Profile"])
async def update_users_me(
    request_data: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user['telegram_id']
    update_data = request_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data provided to update."
        )
    if 'timezone' in update_data:
        await user_repo.set_user_timezone(user_id, update_data['timezone'])
    if 'default_reminder_time' in update_data:
        await user_repo.set_user_default_reminder_time(user_id, update_data['default_reminder_time'])
    if 'pre_reminder_minutes' in update_data:
        await user_repo.set_user_pre_reminder_minutes(user_id, update_data['pre_reminder_minutes'])
    if 'daily_digest_enabled' in update_data:
        await user_repo.set_user_daily_digest_status(user_id, update_data['daily_digest_enabled'])
    if 'daily_digest_time' in update_data:
        await user_repo.set_user_daily_digest_time(user_id, update_data['daily_digest_time'])

    updated_user = await user_repo.get_user_profile(user_id)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found after update.")
    return updated_user

@router.get("/me/achievements", tags=["Profile"])
async def read_my_achievements(current_user: dict = Depends(get_current_user)):
    user_id = current_user['telegram_id']
    all_achievements = await user_repo.get_all_achievements()
    user_achievements_codes = await user_repo.get_user_achievements_codes(user_id)
    result = []
    for ach in all_achievements:
        result.append({
            "code": ach['code'], "name": ach['name'], "description": ach['description'],
            "icon": ach['icon'], "xp_reward": ach['xp_reward'],
            "is_earned": ach['code'] in user_achievements_codes
        })
    return result

@router.post("/me/device", status_code=status.HTTP_201_CREATED, tags=["Profile"])
async def register_device(
    request_data: DeviceTokenRegister,
    current_user: dict = Depends(get_current_user)
):
    """Регистрирует FCM токен устройства для получения push-уведомлений."""
    user_id = current_user['telegram_id']
    await user_repo.register_user_device(
        telegram_id=user_id,
        fcm_token=request_data.fcm_token,
        platform=request_data.platform
    )
    return {"status": "ok", "message": "Device token registered successfully."}