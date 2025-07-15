# src/services/push_service.py
import logging
import os
import json
import httpx
import asyncio
from google.oauth2 import service_account
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

FIREBASE_INITIALIZED = False
PROJECT_ID = None
SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']
FCM_V1_URL_TEMPLATE = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
creds = None


def initialize_firebase():
    """
    Инициализирует Firebase Admin SDK и получает Project ID.
    """
    global FIREBASE_INITIALIZED, PROJECT_ID, creds
    if FIREBASE_INITIALIZED:
        return

    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path or not os.path.exists(creds_path):
        logger.warning(f"Файл ключа '{creds_path}' не найден. Push-уведомления будут отключены.")
        return

    try:
        with open(creds_path, 'r') as f:
            creds_json = json.load(f)
            PROJECT_ID = creds_json.get('project_id')

        if not PROJECT_ID:
            raise ValueError("В файле service-account.json отсутствует 'project_id'.")

        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)

        logger.info(f"Firebase успешно настроен для проекта: {PROJECT_ID}")
        FIREBASE_INITIALIZED = True
    except Exception as e:
        logger.error(f"Ошибка инициализации Firebase: {e}. Push-уведомления будут отключены.")
        FIREBASE_INITIALIZED = False


def get_access_token():
    """Получает или обновляет токен доступа OAuth 2.0."""
    creds.refresh(Request())
    return creds.token


async def send_push_to_user(telegram_id: int, title: str, body: str, data: dict = None):
    if not FIREBASE_INITIALIZED:
        logger.warning("Попытка отправить PUSH, но Firebase не инициализирован.")
        return

    tokens = await user_repo.get_user_device_tokens(telegram_id)
    if not tokens:
        logger.info(f"Для пользователя {telegram_id} не найдено FCM токенов для отправки push.")
        return

    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    fcm_url = FCM_V1_URL_TEMPLATE.format(project_id=PROJECT_ID)

    async with httpx.AsyncClient() as client:
        tasks = [send_single_push(client, fcm_url, headers, token, title, body, data, telegram_id) for token in tokens]
        await asyncio.gather(*tasks)


async def send_single_push(client, url, headers, token, title, body, data, user_id):
    """Отправляет одно уведомление и обрабатывает результат."""
    message_payload = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": data or {},
            "android": {"priority": "high"}
        }
    }
    try:
        response = await client.post(url, headers=headers, json=message_payload, timeout=10)

        if 200 <= response.status_code < 300:
            logger.info(f"Push-уведомление успешно отправлено на токен {token[:15]}... для пользователя {user_id}.")
        else:
            error_data = response.json()
            error_code = error_data.get("error", {}).get("details", [{}])[0].get("errorCode")

            # Логика удаления невалидных токенов
            if error_code in ("UNREGISTERED", "INVALID_ARGUMENT"):
                logger.warning(f"Токен {token[:15]}... невалиден (причина: {error_code}). Удаляем из базы.")
                await user_repo.delete_user_device_token(token)
            else:
                logger.error(
                    f"Ошибка HTTP при отправке push пользователю {user_id}: {response.status_code} - {response.text}")

    except httpx.RequestError as e:
        logger.error(f"Ошибка сети при отправке push пользователю {user_id}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке push пользователю {user_id}: {e}", exc_info=True)


from src.database import user_repo