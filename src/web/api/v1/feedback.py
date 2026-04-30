"""/api/v1/feedback — приём обратной связи из мобилки."""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Feedback, User
from src.db.session import get_session
from src.services.admin_notify import fire_and_forget, fmt_feedback

from .dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    body: str = Field(min_length=1, max_length=4000)
    app_version: Optional[str] = Field(default=None, max_length=32)
    device_info: Optional[str] = Field(default=None, max_length=128)
    screen_at: Optional[str] = Field(default=None, max_length=64)


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    fb = Feedback(
        user_id=user.id,
        sentiment=payload.sentiment,
        body=payload.body,
        app_version=payload.app_version,
        device_info=payload.device_info,
        screen_at=payload.screen_at,
    )
    session.add(fb)
    await session.flush()
    logger.info(
        "feedback received: id=%s user=%s sentiment=%s body=%s",
        fb.id, user.id, payload.sentiment, payload.body[:80],
    )
    fire_and_forget(
        fmt_feedback(
            feedback_id=fb.id,
            sentiment=payload.sentiment,
            body=payload.body,
            user_id=user.id,
            user_email=user.email,
            user_name=user.display_name,
            app_version=payload.app_version,
            device_info=payload.device_info,
        )
    )
    return {"status": "ok"}
