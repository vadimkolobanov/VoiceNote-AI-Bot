# src/web/app.py
from fastapi import FastAPI
from aiogram import Bot

from .routes import handle_alice_request, set_bot_instance
from .models import AliceRequest, AliceResponse


def get_fastapi_app(bot: Bot) -> FastAPI:
    """
    Создает и настраивает экземпляр FastAPI приложения.
    """
    # Устанавливаем экземпляр бота, чтобы его можно было использовать в роутах
    set_bot_instance(bot)

    # Создаем приложение без стандартной документации
    app = FastAPI(docs_url=None, redoc_url=None)

    # Регистрируем основной роут для вебхука Алисы
    @app.post("/alice_webhook")
    async def alice_webhook_endpoint(request: AliceRequest) -> AliceResponse:
        return await handle_alice_request(request)

    return app