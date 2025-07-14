# src/web/app.py
from fastapi import FastAPI
from aiogram import Bot

from .routes import handle_alice_request, set_bot_instance
from .models import AliceRequest, AliceResponse
from .api.auth import router as auth_router
from .api.profile import router as profile_router
from .api.notes import router as notes_router
from .api.birthdays import router as birthdays_router


def get_fastapi_app(bot: Bot) -> FastAPI:
    """
    Создает и настраивает экземпляр FastAPI приложения.
    """
    # Устанавливаем экземпляр бота для вебхука Алисы
    set_bot_instance(bot)

    app = FastAPI(
        title="VoiceNote AI API",
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc"
    )

    # --- Роутер для вебхука Алисы (в корне) ---
    @app.post("/alice_webhook")
    async def alice_webhook_endpoint(request: AliceRequest) -> AliceResponse:
        return await handle_alice_request(request)

    # --- Подключаем все наши API-роутеры ---

    # Роутер для проверки состояния API (health check)
    @app.get("/api/v1/health", tags=["Health Check"])
    async def health_check():
        return {"status": "OK"}

    # Роутер для аутентификации
    app.include_router(
        auth_router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )

    # Роутер для профиля пользователя
    app.include_router(
        profile_router,
        prefix="/api/v1/profile",
        tags=["Profile"]
    )

    # Роутер для заметок
    app.include_router(
        notes_router,
        prefix="/api/v1/notes",
        tags=["Notes"]
    )

    # Роутер для дней рождения
    app.include_router(
        birthdays_router,
        prefix="/api/v1/birthdays",
        tags=["Birthdays"]
    )

    return app