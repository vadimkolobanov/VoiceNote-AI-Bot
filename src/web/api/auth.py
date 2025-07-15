# src/web/api/auth.py
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.core.config import TG_BOT_TOKEN, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES
from src.database import user_repo
from .schemas import TelegramLoginData, Token
from jose import jwt

router = APIRouter()


def check_telegram_authorization(bot_token: str, auth_data: dict) -> bool:
    """
    Проверяет данные, полученные от Telegram Login Widget.
    """
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

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Создает JWT токен."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


@router.post("/login", response_model=Token, tags=["Authentication"])
async def login_with_telegram(login_data: TelegramLoginData):
    """
    Принимает данные от Telegram Login, верифицирует их и возвращает JWT токен.
    """
    data_dict = login_data.model_dump(exclude_unset=True)

    try:
        if not check_telegram_authorization(bot_token=TG_BOT_TOKEN, auth_data=data_dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram login data",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not validate Telegram data",
        )

    user = await user_repo.get_or_create_user(login_data)
    if not user:
        raise HTTPException(status_code=500, detail="Could not create or get user")

    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user['telegram_id'])}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


class CodeLoginRequest(BaseModel):
    code: str


@router.post("/code", response_model=Token, tags=["Authentication"])
async def login_with_code(request: CodeLoginRequest):
    code = request.code.strip().upper()
    user = await user_repo.find_user_by_mobile_code(code)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired code. Please get a new one from the bot."
        )

    # Очищаем код, чтобы его нельзя было использовать повторно
    await user_repo.clear_mobile_activation_code(user['telegram_id'])

    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user['telegram_id'])}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}