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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        telegram_id_str: str = payload.get("sub")
        if telegram_id_str is None:
            raise credentials_exception

        # Проверяем срок действия токена
        expire_timestamp = payload.get("exp")
        if expire_timestamp is None or datetime.now(timezone.utc) > datetime.fromtimestamp(expire_timestamp,
                                                                                           tz=timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

        token_data = TokenData(sub=telegram_id_str)
    except (JWTError, ValidationError):
        raise credentials_exception

    user = await user_repo.get_user_profile(int(token_data.sub))
    if user is None:
        raise credentials_exception

    return user