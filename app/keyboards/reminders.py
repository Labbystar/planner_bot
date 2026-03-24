from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def reminder_actions(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done:{reminder_id}"),
            InlineKeyboardButton(text="⏰ Отложить", callback_data=f"snzmenu:{reminder_id}"),
        ],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{reminder_id}")],
    ])


def snooze_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="+5 мин", callback_data=f"snz:{reminder_id}:5"), InlineKeyboardButton(text="+15 мин", callback_data=f"snz:{reminder_id}:15")],
        [InlineKeyboardButton(text="+1 час", callback_data=f"snz:{reminder_id}:60")],
    ])


def pager(page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    buttons = []
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{page-1}"))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{page+1}"))
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def settings_kb(enabled: bool) -> InlineKeyboardMarkup:
    label = "🌙 Тихие часы: вкл" if enabled else "🌙 Тихие часы: выкл"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕓 Показать мое время", callback_data="sett:time")],
        [InlineKeyboardButton(text="🌍 Показать таймзону", callback_data="sett:tz")],
        [InlineKeyboardButton(text="Новосибирск", callback_data="tz:Asia/Novosibirsk"), InlineKeyboardButton(text="Москва", callback_data="tz:Europe/Moscow")],
        [InlineKeyboardButton(text=label, callback_data="sett:quiet")],
    ])
