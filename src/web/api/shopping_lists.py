"""
Shopping lists API (Phase 1 rewrite).

Эндпоинты:
  GET    /api/v1/shopping-lists               — все списки пользователя
  POST   /api/v1/shopping-lists               — создать новый
  GET    /api/v1/shopping-lists/{id}          — список + items + members
  PATCH  /api/v1/shopping-lists/{id}          — переименовать
  DELETE /api/v1/shopping-lists/{id}          — удалить (только owner)
  POST   /api/v1/shopping-lists/{id}/archive  — в архив
  POST   /api/v1/shopping-lists/{id}/restore  — из архива
  POST   /api/v1/shopping-lists/{id}/items              — добавить товар
  PATCH  /api/v1/shopping-lists/items/{item_id}         — чекнуть/снять
  DELETE /api/v1/shopping-lists/items/{item_id}         — удалить товар
  POST   /api/v1/shopping-lists/{id}/invites   — создать 6-значный код
  POST   /api/v1/shopping-lists/join           — вступить по коду
  POST   /api/v1/shopping-lists/{id}/leave     — выйти (не owner)
  DELETE /api/v1/shopping-lists/{id}/members/{user_id} — исключить (owner)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.database import shopping_repo
from .dependencies import get_current_user

router = APIRouter(prefix="/shopping-lists", tags=["Shopping Lists"])


# ----- Schemas -----

class ListSummary(BaseModel):
    id: int
    owner_id: int
    title: str
    created_at: str
    archived_at: str | None = None
    items_count: int
    checked_count: int


class Member(BaseModel):
    user_id: int
    role: str
    joined_at: str
    first_name: str | None = None
    username: str | None = None


class Item(BaseModel):
    id: int
    name: str
    quantity: str | None = None
    position: int
    checked_at: str | None = None
    checked_by: int | None = None
    added_by: int
    created_at: str


class ListDetail(BaseModel):
    id: int
    owner_id: int
    title: str
    created_at: str
    archived_at: str | None = None
    items: list[Item]
    members: list[Member]


class CreateListRequest(BaseModel):
    title: str = Field(default="Список покупок", min_length=0, max_length=120)


class RenameListRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class AddItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=60)


class ToggleItemRequest(BaseModel):
    checked: bool


class InviteResponse(BaseModel):
    code: str
    expires_at: str


class JoinRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=10)


# ----- Helpers -----

def _iso(v) -> str | None:
    return v.isoformat() if v else None


def _row_to_summary(row: dict) -> dict:
    return {
        **row,
        "created_at": _iso(row["created_at"]),
        "archived_at": _iso(row.get("archived_at")),
    }


def _row_to_item(row: dict) -> dict:
    return {
        **row,
        "checked_at": _iso(row.get("checked_at")),
        "created_at": _iso(row["created_at"]),
    }


def _row_to_member(row: dict) -> dict:
    return {
        **row,
        "joined_at": _iso(row["joined_at"]),
    }


# ----- Lists -----

@router.get("", response_model=list[ListSummary])
async def list_lists(
    include_archived: bool = False,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    rows = await shopping_repo.list_user_lists(current_user["telegram_id"], include_archived)
    return [_row_to_summary(r) for r in rows]


@router.post("", response_model=ListDetail, status_code=status.HTTP_201_CREATED)
async def create_list(
    payload: CreateListRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    new_id = await shopping_repo.create_list(current_user["telegram_id"], payload.title)
    detail = await shopping_repo.get_list(new_id, current_user["telegram_id"])
    return _serialize_detail(detail)


@router.get("/{list_id}", response_model=ListDetail)
async def get_list_detail(
    list_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    detail = await shopping_repo.get_list(list_id, current_user["telegram_id"])
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Список не найден или нет доступа")
    return _serialize_detail(detail)


@router.patch("/{list_id}", response_model=ListDetail)
async def rename_list(
    list_id: int,
    payload: RenameListRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    ok = await shopping_repo.rename_list(list_id, current_user["telegram_id"], payload.title)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Список не найден или нет доступа")
    return _serialize_detail(await shopping_repo.get_list(list_id, current_user["telegram_id"]))


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_list(
    list_id: int,
    current_user: dict = Depends(get_current_user),
) -> Response:
    ok = await shopping_repo.delete_list(list_id, current_user["telegram_id"])
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Только владелец может удалить список")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{list_id}/archive", response_model=ListDetail)
async def archive(
    list_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    ok = await shopping_repo.archive_list(list_id, current_user["telegram_id"])
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Список не найден или нет прав")
    return _serialize_detail(await shopping_repo.get_list(list_id, current_user["telegram_id"]))


@router.post("/{list_id}/restore", response_model=ListDetail)
async def restore(
    list_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    ok = await shopping_repo.restore_list(list_id, current_user["telegram_id"])
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Список не найден или не в архиве")
    return _serialize_detail(await shopping_repo.get_list(list_id, current_user["telegram_id"]))


# ----- Items -----

@router.post("/{list_id}/items", response_model=Item, status_code=status.HTTP_201_CREATED)
async def add_item(
    list_id: int,
    payload: AddItemRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    row = await shopping_repo.add_item(
        list_id, current_user["telegram_id"], payload.name, payload.quantity
    )
    if not row:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этому списку")
    return _row_to_item(row)


@router.patch("/items/{item_id}", response_model=Item)
async def toggle_item(
    item_id: int,
    payload: ToggleItemRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    row = await shopping_repo.toggle_item(item_id, current_user["telegram_id"], payload.checked)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден или нет доступа")
    return _row_to_item(row)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
) -> Response:
    ok = await shopping_repo.delete_item(item_id, current_user["telegram_id"])
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден или нет доступа")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- Invites / members -----

@router.post("/{list_id}/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    list_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    invite = await shopping_repo.create_invite(list_id, current_user["telegram_id"])
    if not invite:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к списку")
    return {
        "code": invite["code"],
        "expires_at": _iso(invite["expires_at"]),
    }


class JoinResponse(BaseModel):
    list_id: int


@router.post("/join", response_model=JoinResponse)
async def join(
    payload: JoinRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    result = await shopping_repo.consume_invite(payload.code, current_user["telegram_id"])
    if result is None or "error" in result:
        err = (result or {}).get("error", "not_found")
        messages = {
            "not_found": "Код не найден",
            "already_used": "Код уже использован",
            "expired": "Срок кода истёк",
        }
        raise HTTPException(status.HTTP_400_BAD_REQUEST, messages.get(err, "Неверный код"))
    return {"list_id": result["list_id"]}


@router.post("/{list_id}/leave", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def leave(
    list_id: int,
    current_user: dict = Depends(get_current_user),
) -> Response:
    ok = await shopping_repo.leave_list(list_id, current_user["telegram_id"])
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Владелец не может выйти; удалите список")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{list_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_member(
    list_id: int,
    user_id: int,
    current_user: dict = Depends(get_current_user),
) -> Response:
    ok = await shopping_repo.remove_member(list_id, current_user["telegram_id"], user_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет доступа или участник не найден")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- Serializer helpers -----

def _serialize_detail(detail: dict) -> dict:
    return {
        "id": detail["id"],
        "owner_id": detail["owner_id"],
        "title": detail["title"],
        "created_at": _iso(detail["created_at"]),
        "archived_at": _iso(detail.get("archived_at")),
        "items": [_row_to_item(i) for i in detail.get("items", [])],
        "members": [_row_to_member(m) for m in detail.get("members", [])],
    }
