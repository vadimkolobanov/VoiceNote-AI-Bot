# src/bot/modules/admin/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.common_utils.callbacks import AdminAction, AdminUserNav


def get_admin_user_panel_keyboard(target_user_id: int, is_vip: bool) -> InlineKeyboardMarkup:
    """Клавиатура для управления конкретным пользователем."""
    builder = InlineKeyboardBuilder()
    toggle_vip_text = "❌ Забрать VIP" if is_vip else "✅ Выдать VIP"
    builder.button(
        text=toggle_vip_text,
        callback_data=AdminAction(
            action="toggle_vip",
            target_user_id=target_user_id,
            current_vip_status=int(is_vip)
        ).pack()
    )
    builder.button(
        text="⬅️ К списку пользователей",
        callback_data=AdminUserNav(page=1).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_admin_users_list_keyboard(users: list[dict], current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура со списком пользователей и кнопками пагинации."""
    builder = InlineKeyboardBuilder()
    for user in users:
        vip_icon = "👑" if user.get('is_vip') else ""
        user_name = user.get('first_name') or f"ID: {user['telegram_id']}"
        preview_text = f"{vip_icon} {user_name} (@{user.get('username', 'N/A')})"
        builder.button(
            text=preview_text,
            callback_data=AdminAction(
                action="show_info",
                target_user_id=user['telegram_id']
            ).pack()
        )
    builder.adjust(1)

    pagination_row = []
    if current_page > 1:
        pagination_row.append(
            InlineKeyboardButton(text="⬅️", callback_data=AdminUserNav(page=current_page - 1).pack())
        )
    if total_pages > 1:
        pagination_row.append(
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="ignore")
        )
    if current_page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(text="➡️", callback_data=AdminUserNav(page=current_page + 1).pack())
        )

    if pagination_row:
        builder.row(*pagination_row)

    return builder.as_markup()