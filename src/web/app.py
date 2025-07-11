# src/web/app.py
from fastapi import FastAPI
from aiogram import Bot

from .routes import handle_alice_request, set_bot_instance
from .models import AliceRequest, AliceResponse
from .api.auth import router as auth_router
from .api.profile import router as profile_router


def get_fastapi_app(bot: Bot) -> FastAPI:
    """
    Создает и настраивает экземпляр FastAPI приложения.
    """
    # Устанавливаем экземпляр бота, чтобы его можно было использовать в роутах
    set_bot_instance(bot)

    # Создаем приложение
    app = FastAPI(
        title="VoiceNote AI API",
        version="1.0.0"
    )

    # --- Подключаем роутеры ---

    # Роутер для вебхука Алисы (остается в корне)
    @app.post("/alice_webhook")
    async def alice_webhook_endpoint(request: AliceRequest) -> AliceResponse:
        return await handle_alice_request(request)

    # Подключаем API-роутеры с общим префиксом /api/v1
    app.include_router(
        auth_router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    app.include_router(
        profile_router,
        prefix="/api/v1/profile",
        tags=["Profile"]
    )

    @app.get("/api/v1/health", tags=["Health Check"])
    async def health_check():
        return {"status": "OK"}

    return app