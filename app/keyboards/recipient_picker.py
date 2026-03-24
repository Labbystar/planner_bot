from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def recipient_picker_kb(users, selected_ids: list[int], page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    selected = set(selected_ids)
    start = page * per_page
    chunk = users[start:start + per_page]
    rows: list[list[InlineKeyboardButton]] = []
    for user in chunk:
        name = user.username and f"@{user.username}" or user.full_name or str(user.user_id)
        prefix = "✅" if user.user_id in selected else "⬜"
        rows.append([InlineKeyboardButton(text=f"{prefix} {name}", callback_data=f"recipient_toggle:{user.user_id}:{page}")])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"recipient_page:{page-1}"))
    if start + per_page < len(users):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"recipient_page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="👥 Импорт из группы", callback_data="recipient_group_pick")])
    rows.append([InlineKeyboardButton(text="✍️ Ввести ID вручную", callback_data="recipient_manual")])
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="recipient_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
