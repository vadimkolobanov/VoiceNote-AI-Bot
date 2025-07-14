# src/web/api/birthdays.py
import re
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status

from src.database import birthday_repo
from src.core.config import NOTES_PER_PAGE
from .dependencies import get_current_user
from .schemas import PaginatedBirthdaysResponse, Birthday, BirthdayCreateRequest

router = APIRouter()

def parse_date(date_str: str) -> tuple[int, int, int | None] | None:
    date_str = date_str.strip()
    match_full = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", date_str)
    if match_full:
        day, month, year = map(int, match_full.groups())
        try:
            datetime(year, month, day)
            return day, month, year
        except ValueError:
            return None

    match_short = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})", date_str)
    if match_short:
        day, month = map(int, match_short.groups())
        try:
            datetime(2000, month, day)
            return day, month, None
        except ValueError:
            return None
    return None

@router.get("", response_model=PaginatedBirthdaysResponse, tags=["Birthdays"])
async def get_birthdays(
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
):
    user_id = current_user['telegram_id']
    birthdays, total_items = await birthday_repo.get_birthdays_for_user(
        telegram_id=user_id,
        page=page,
        per_page=per_page
    )
    total_pages = (total_items + per_page - 1) // per_page
    if total_pages == 0:
        total_pages = 1
    return {
        "items": birthdays,
        "total": total_items,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }

@router.post("", response_model=Birthday, status_code=status.HTTP_201_CREATED, tags=["Birthdays"])
async def create_birthday(
    request_data: BirthdayCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user['telegram_id']
    parsed_date = parse_date(request_data.birth_date)
    if not parsed_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use DD.MM.YYYY or DD.MM"
        )
    day, month, year = parsed_date
    new_birthday = await birthday_repo.add_birthday(
        user_telegram_id=user_id,
        person_name=request_data.person_name,
        day=day,
        month=month,
        year=year
    )
    if not new_birthday:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create birthday")
    return new_birthday

@router.delete("/{birthday_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Birthdays"])
async def delete_birthday(birthday_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user['telegram_id']
    # Проверим, что запись существует, перед удалением (birthday_repo.delete_birthday это делает внутри)
    success = await birthday_repo.delete_birthday(birthday_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Birthday not found or you are not the owner"
        )
    return None