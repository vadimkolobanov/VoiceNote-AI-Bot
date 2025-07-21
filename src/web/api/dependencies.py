# src/web/api/dependencies.py
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from src.core.config import JWT_SECRET_KEY, JWT_ALGORITHM, INTERNAL_API_KEY
from src.database import user_repo


class TokenData(BaseModel):
    sub: str | None = None


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
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


async def get_user_for_internal_api(
        request: Request,
        x_internal_api_key: str | None = Header(None)
) -> dict:
    if not INTERNAL_API_KEY or x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal API key")

    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        if not telegram_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="telegram_id is required for internal requests")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body or missing telegram_id")

    user = await user_repo.get_user_profile(int(telegram_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user