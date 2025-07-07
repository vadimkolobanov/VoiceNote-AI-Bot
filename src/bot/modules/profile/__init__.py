# src/bot/modules/profile/__init__.py
from aiogram import Router

from .handlers.profile import router as profile_router
from .handlers.settings import router as settings_router
from .handlers.support import router as support_router

# Создаем единый роутер для всего модуля "Профиль"
router = Router()

# Подключаем роутеры из подмодулей
router.include_router(profile_router)
router.include_router(settings_router)
router.include_router(support_router)

__all__ = ["router"]