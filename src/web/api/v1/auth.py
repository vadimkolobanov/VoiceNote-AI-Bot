"""/api/v1/auth/* — email/password flow (docs/PRODUCT_PLAN.md §5.2).

MVP-пара endpoint'ов: register/login/refresh/logout/delete. Password reset
(``/reset/request`` + ``/reset/confirm``) по плану тоже в M1, но требует
email-провайдера — оставляем каркас без отправки почты: POST принимается,
клиент видит 204, фактическая отправка появится в M7 (где и push-инфра).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.session import get_session
from src.services import auth_service
from src.services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
)

from .dependencies import get_current_user
from .schemas import (
    EmailLoginRequest,
    EmailRegisterRequest,
    LogoutRequest,
    RefreshRequest,
    TokenPairResponse,
    TokenRefreshResponse,
    UserPublic,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        timezone=user.timezone,
        locale=user.locale,
        digest_hour=user.digest_hour,
        is_pro=user.is_pro(),
        created_at=user.created_at,
    )


# --- email register / login -----------------------------------------------


@router.post(
    "/email/register",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_email(
    payload: EmailRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    try:
        pair = await auth_service.register_user(
            session,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "EMAIL_ALREADY_REGISTERED",
                    "message": "Email уже зарегистрирован",
                }
            },
        )
    return TokenPairResponse(
        access=pair.access, refresh=pair.refresh, user=_user_to_public(pair.user)
    )


@router.post("/email/login", response_model=TokenPairResponse)
async def login_email(
    payload: EmailLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    try:
        pair = await auth_service.login_user(
            session, email=payload.email, password=payload.password
        )
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Неверный email или пароль",
                }
            },
        )
    return TokenPairResponse(
        access=pair.access, refresh=pair.refresh, user=_user_to_public(pair.user)
    )


# --- refresh / logout -----------------------------------------------------


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_tokens(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenRefreshResponse:
    try:
        pair = await auth_service.refresh_tokens(
            session, refresh_token=payload.refresh
        )
    except InvalidRefreshToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "Refresh token недействителен или истёк",
                }
            },
        )
    return TokenRefreshResponse(access=pair.access, refresh=pair.refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(get_current_user),
) -> Response:
    await auth_service.logout(session, refresh_token=payload.refresh)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- reset (stub until M7) ------------------------------------------------


class ResetRequestBody(BaseModel):
    email: EmailStr


class ResetConfirmBody(BaseModel):
    token: str
    new_password: str


@router.post("/reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def reset_request(_body: ResetRequestBody) -> Response:
    """§5.2 ``POST /auth/reset/request``.

    Всегда возвращаем 204 (не подтверждаем существование email для
    anti-enumeration). Фактическая отправка письма — в M7 (email-провайдер
    ещё не выбран).
    """
    logger.info("auth.reset.request accepted (email send pending M7)")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def reset_confirm(_body: ResetConfirmBody) -> Response:
    """§5.2 ``POST /auth/reset/confirm``. Stub до реализации email-flow в M7."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": "Password reset появится в M7 вместе с email-провайдером",
            }
        },
    )


# --- self-delete ----------------------------------------------------------


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    """§5.2 ``POST /auth/delete``. Soft-delete + revoke all refresh tokens.

    Фактическое каскадное удаление данных — через 14 дней, в отдельном job
    (M7+, см. §10.1).
    """
    await auth_service.soft_delete_user(session, user_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
