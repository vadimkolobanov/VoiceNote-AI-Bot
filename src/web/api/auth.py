# src/web/api/auth.py
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from src.core.config import TG_BOT_TOKEN, JWT_SECRET_KEY, JWT_ALGORITHM
from src.database import user_repo
from src.database.connection import get_db_pool
from .schemas import TelegramLoginData, Token
from .dependencies import get_current_user
from jose import jwt

router = APIRouter()

# Настройки времени жизни токенов
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30


def check_telegram_authorization(bot_token: str, auth_data: dict) -> bool:
    """Проверяет данные, полученные от Telegram Login Widget."""
    check_hash = auth_data['hash']

    data_check_string_parts = []
    for key in sorted(auth_data.keys()):
        if key != 'hash':
            value = unquote(str(auth_data[key]))
            data_check_string_parts.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_string_parts)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return calculated_hash == check_hash


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Создает JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token() -> str:
    """Генерирует криптографически безопасный refresh token."""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """Хеширует refresh token для хранения в БД."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _store_refresh_token(user_telegram_id: int, token: str) -> None:
    """Сохраняет refresh token в БД."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO refresh_tokens (token_hash, user_telegram_id, expires_at)
            VALUES ($1, $2, $3)
            """,
            hash_token(token),
            user_telegram_id,
            datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )


async def _validate_refresh_token(token: str) -> int | None:
    """Проверяет refresh token и возвращает telegram_id или None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_telegram_id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token_hash = $1
            """,
            hash_token(token)
        )
    if not row:
        return None
    if row['revoked_at'] is not None:
        return None
    if row['expires_at'] < datetime.now(timezone.utc):
        return None
    return row['user_telegram_id']


async def _revoke_refresh_token(token: str) -> None:
    """Отзывает refresh token."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens SET revoked_at = NOW()
            WHERE token_hash = $1 AND revoked_at IS NULL
            """,
            hash_token(token)
        )


async def _revoke_all_user_tokens(user_telegram_id: int) -> None:
    """Отзывает все refresh-токены пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens SET revoked_at = NOW()
            WHERE user_telegram_id = $1 AND revoked_at IS NULL
            """,
            user_telegram_id
        )


async def _issue_tokens(telegram_id: int) -> dict:
    """Выпускает пару access + refresh токенов."""
    access_token = create_access_token(
        data={"sub": str(telegram_id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token()
    await _store_refresh_token(telegram_id, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


# --- Endpoints ---

@router.post("/login", response_model=Token, tags=["Authentication"])
async def login_with_telegram(login_data: TelegramLoginData):
    """Принимает данные от Telegram Login, верифицирует и возвращает JWT + refresh token."""
    data_dict = login_data.model_dump(exclude_unset=True)

    try:
        if not check_telegram_authorization(bot_token=TG_BOT_TOKEN, auth_data=data_dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram login data",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not validate Telegram data",
        )

    user = await user_repo.get_or_create_user(login_data)
    if not user:
        raise HTTPException(status_code=500, detail="Could not create or get user")

    return await _issue_tokens(user['telegram_id'])


class CodeLoginRequest(BaseModel):
    code: str


@router.post("/code", response_model=Token, tags=["Authentication"])
async def login_with_code(request: CodeLoginRequest):
    """Авторизация по одноразовому коду из Telegram-бота."""
    code = request.code.strip().upper()
    user = await user_repo.find_user_by_mobile_code(code)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired code. Please get a new one from the bot."
        )

    await user_repo.clear_mobile_activation_code(user['telegram_id'])
    return await _issue_tokens(user['telegram_id'])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=Token, tags=["Authentication"])
async def refresh_tokens(request: RefreshTokenRequest):
    """Обновляет пару токенов по refresh token (rotation)."""
    telegram_id = await _validate_refresh_token(request.refresh_token)
    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )

    # Отзываем старый refresh token (rotation)
    await _revoke_refresh_token(request.refresh_token)

    return await _issue_tokens(telegram_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Authentication"])
async def logout(
        request: RefreshTokenRequest,
        current_user: dict = Depends(get_current_user)
):
    """Отзывает refresh token при логауте."""
    await _revoke_refresh_token(request.refresh_token)
