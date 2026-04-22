# src/web/api/habits.py
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.database import habit_repo
from src.services.llm import extract_habits_from_text
from .dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---

class HabitResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    frequency_rule: str
    reminder_time: str | None = None
    is_active: bool

    class Config:
        from_attributes = True


class HabitCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Описание привычек естественным языком")


class HabitTrackRequest(BaseModel):
    track_date: date | None = None
    habit_status: str = Field(default="done", pattern="^(done|skipped)$")


class HabitStatsEntry(BaseModel):
    track_date: date
    status: str


# --- Endpoints ---

@router.get("/", response_model=list[HabitResponse], tags=["Habits"])
async def list_habits(current_user: dict = Depends(get_current_user)):
    """Возвращает список активных привычек пользователя."""
    habits = await habit_repo.get_user_habits(current_user['telegram_id'])
    result = []
    for h in habits:
        result.append({
            **h,
            "reminder_time": h['reminder_time'].strftime('%H:%M') if h.get('reminder_time') else None,
        })
    return result


@router.post("/", response_model=list[HabitResponse], status_code=status.HTTP_201_CREATED, tags=["Habits"])
async def create_habits(
        request: HabitCreateRequest,
        current_user: dict = Depends(get_current_user)
):
    """Создает привычки из текстового описания через LLM."""
    user_id = current_user['telegram_id']

    parsed_habits = await extract_habits_from_text(request.text)
    if not parsed_habits:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Не удалось распознать привычки из текста. Попробуйте описать конкретнее."
        )

    created = await habit_repo.add_habits_bulk(user_id, parsed_habits)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при сохранении привычек."
        )

    result = []
    for h in created:
        result.append({
            **h,
            "reminder_time": h['reminder_time'].strftime('%H:%M') if h.get('reminder_time') else None,
        })
    return result


@router.post("/{habit_id}/track", status_code=status.HTTP_200_OK, tags=["Habits"])
async def track_habit(
        habit_id: int,
        request: HabitTrackRequest,
        current_user: dict = Depends(get_current_user)
):
    """Отмечает привычку выполненной или пропущенной."""
    user_id = current_user['telegram_id']
    track_date = request.track_date or date.today()

    success = await habit_repo.track_habit(
        habit_id=habit_id,
        user_telegram_id=user_id,
        track_date=track_date,
        status=request.habit_status
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при записи трекинга."
        )

    return {"detail": "Tracked successfully.", "habit_id": habit_id, "date": str(track_date), "status": request.habit_status}


@router.get("/{habit_id}/stats", tags=["Habits"])
async def get_habit_stats(
        habit_id: int,
        days: int = 7,
        current_user: dict = Depends(get_current_user)
):
    """Возвращает статистику привычки за последние N дней.

    Форматируем даты в ISO-строки, чтобы фронт парсил через `DateTime.parse`.
    """
    start_date = date.today() - timedelta(days=days)
    try:
        stats = await habit_repo.get_weekly_stats(habit_id, start_date)
    except Exception as e:
        logger.exception("Failed to load habit stats for habit_id=%s: %s", habit_id, e)
        return []
    return [
        {
            "date": row["track_date"].isoformat() if row.get("track_date") else None,
            "status": row.get("status") or "done",
        }
        for row in stats
    ]


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Habits"])
async def delete_habit(
        habit_id: int,
        current_user: dict = Depends(get_current_user)
):
    """Удаляет привычку."""
    user_id = current_user['telegram_id']
    success = await habit_repo.delete_habit(habit_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Привычка не найдена или не принадлежит вам."
        )
