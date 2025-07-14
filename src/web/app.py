# src/web/app.py
from fastapi import FastAPI
from aiogram import Bot
from starlette.responses import HTMLResponse

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

    @app.get("/auth/callback", response_class=HTMLResponse)
    async def telegram_auth_callback():
        return """
        <html>
          <head>
            <meta charset="UTF-8">
            <title>VoiceNote AI Login</title>
          </head>
          <body>
            <h2>Авторизация через Telegram...</h2>
            <script>
              // Извлекаем параметры из URL-фрагмента
              const hash = window.location.hash.substring(1);
              if (hash) {
                // Отправляем данные на API
                fetch("/api/v1/auth/login", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(Object.fromEntries(new URLSearchParams(hash)))
                })
                .then(res => res.json())
                .then(data => {
                  if (data.access_token) {
                    window.ReactNativeWebView.postMessage(JSON.stringify(data));
                  } else {
                    window.ReactNativeWebView.postMessage(JSON.stringify({ error: 'Login failed' }));
                  }
                });
              }
            </script>
          </body>
        </html>
        """

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