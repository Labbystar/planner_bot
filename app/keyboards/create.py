from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Работа", callback_data="cat:work"), InlineKeyboardButton(text="📂 Личное", callback_data="cat:personal")],
        [InlineKeyboardButton(text="📂 Финансы", callback_data="cat:finance"), InlineKeyboardButton(text="📂 Важное", callback_data="cat:important")],
    ])


def priorities_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Низкий", callback_data="prio:low")],
        [InlineKeyboardButton(text="🟡 Средний", callback_data="prio:medium")],
        [InlineKeyboardButton(text="🔴 Высокий", callback_data="prio:high")],
    ])


def note_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово с вложениями", callback_data="note:done")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="note:skip")],
    ])


def assignee_kb(users: list[dict], selected_user_id: int) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton(text="✅ Назначить себе", callback_data=f"assign:{selected_user_id}")])
    for user in users[:10]:
        label = f"@{user['username']}" if user.get('username') else user.get('full_name') or str(user['user_id'])
        rows.append([InlineKeyboardButton(text=f"👤 {label}", callback_data=f"assign:{user['user_id']}")])
    rows.append([InlineKeyboardButton(text="✍️ Ввести ID вручную", callback_data="assign:manual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
