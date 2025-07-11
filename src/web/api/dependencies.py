# src/web/api/dependencies.py
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from src.core.config import JWT_SECRET_KEY, JWT_ALGORITHM
from src.database import user_repo


class TokenData(BaseModel):
    sub: str | None = None


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Проверяет JWT токен и возвращает данные текущего пользователя.
    """
    # ЛОГИРОВАНИЕ: Смотрим, какой токен пришел
    print(f"[API Deps] Попытка верификации токена: {token[:15]}...")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        telegram_id_str: str = payload.get("sub")
        if telegram_id_str is None:
            print("[API Deps] Ошибка: 'sub' отсутствует в токене.")
            raise credentials_exception

        expire_timestamp = payload.get("exp")
        if expire_timestamp is None or datetime.now(timezone.utc) > datetime.fromtimestamp(expire_timestamp,
                                                                                           tz=timezone.utc):
            print("[API Deps] Ошибка: Срок действия токена истек.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

        token_data = TokenData(sub=telegram_id_str)
    except (JWTError, ValidationError) as e:
        print(f"[API Deps] Ошибка декодирования JWT: {e}")
        raise credentials_exception

    user = await user_repo.get_user_profile(int(token_data.sub))
    if user is None:
        print(f"[API Deps] Ошибка: Пользователь с ID {token_data.sub} не найден в БД.")
        raise credentials_exception

    print(f"[API Deps] Успешная аутентификация пользователя {user['telegram_id']}")
    return user