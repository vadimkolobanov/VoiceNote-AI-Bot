# src/web/app.py
from fastapi import FastAPI
from aiogram import Bot

from .routes import handle_alice_request, set_bot_instance
from .models import AliceRequest, AliceResponse
from .api.auth import router as auth_router
from .api.profile import router as profile_router
from .api.notes import router as notes_router
from .api.birthdays import router as birthdays_router  # <--- ИМПОРТ


def get_fastapi_app(bot: Bot) -> FastAPI:
    set_bot_instance(bot)

    app = FastAPI(
        title="VoiceNote AI API",
        version="1.0.0",
        docs_url="/api/v1/docs",  # Перенесем документацию для порядка
        redoc_url="/api/v1/redoc"
    )

    @app.post("/alice_webhook")
    async def alice_webhook_endpoint(request: AliceRequest) -> AliceResponse:
        return await handle_alice_request(request)

    @app.get("/api/v1/health", tags=["Health Check"])
    async def health_check():
        return {"status": "OK"}

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

    app.include_router(
        notes_router,
        prefix="/api/v1/notes",
        tags=["Notes"]
    )

    # --- ПОДКЛЮЧАЕМ НОВЫЙ РОУТЕР ---
    app.include_router(
        birthdays_router,
        prefix="/api/v1/birthdays",
        tags=["Birthdays"]
    )

    return app