# src/bot/modules/notes/__init__.py
from aiogram import Router

# Импортируем роутеры из всех подмодулей хендлеров
from .handlers.actions import router as actions_router
from .handlers.creation import router as creation_router
from .handlers.edit import router as edit_router
from .handlers.list_view import router as list_view_router
from .handlers.shopping_list import router as shopping_list_router

# Создаем один "главный" роутер для всего модуля "notes"
router = Router()

# Порядок подключения важен. Сначала более специфичные.
# Роутер создания должен идти раньше, чем общие действия,
# чтобы F.text не перехватывал всё подряд.
router.include_router(creation_router)
router.include_router(list_view_router)
router.include_router(shopping_list_router)
router.include_router(edit_router)
router.include_router(actions_router)


__all__ = ["router"]