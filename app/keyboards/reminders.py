from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def reminder_actions(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done:{reminder_id}"),
            InlineKeyboardButton(text="⏰ Отложить", callback_data=f"snzmenu:{reminder_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"edittext:{reminder_id}"),
            InlineKeyboardButton(text="🕓 Время", callback_data=f"edittime:{reminder_id}"),
        ],
        [
            InlineKeyboardButton(text="📂 Категория", callback_data=f"editcatmenu:{reminder_id}"),
            InlineKeyboardButton(text="🚦 Приоритет", callback_data=f"editpriomenu:{reminder_id}"),
        ],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{reminder_id}")],
    ])


def snooze_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="+5 мин", callback_data=f"snz:{reminder_id}:5"), InlineKeyboardButton(text="+15 мин", callback_data=f"snz:{reminder_id}:15")],
        [InlineKeyboardButton(text="+1 час", callback_data=f"snz:{reminder_id}:60")],
    ])


def category_edit_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Работа", callback_data=f"editcat:{reminder_id}:work"), InlineKeyboardButton(text="📂 Личное", callback_data=f"editcat:{reminder_id}:personal")],
        [InlineKeyboardButton(text="📂 Финансы", callback_data=f"editcat:{reminder_id}:finance"), InlineKeyboardButton(text="📂 Важное", callback_data=f"editcat:{reminder_id}:important")],
    ])


def priority_edit_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Низкий", callback_data=f"editprio:{reminder_id}:low")],
        [InlineKeyboardButton(text="🟡 Средний", callback_data=f"editprio:{reminder_id}:medium")],
        [InlineKeyboardButton(text="🔴 Высокий", callback_data=f"editprio:{reminder_id}:high")],
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
        [InlineKeyboardButton(text="🗑 Удалить профиль", callback_data="sett:delete")],
    ])


def active_filters_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Все", callback_data="flt:all"),
            InlineKeyboardButton(text="Работа", callback_data="flt:work"),
            InlineKeyboardButton(text="Личное", callback_data="flt:personal"),
        ],
        [
            InlineKeyboardButton(text="Финансы", callback_data="flt:finance"),
            InlineKeyboardButton(text="Важное", callback_data="flt:important"),
            InlineKeyboardButton(text="🔴 High", callback_data="fltprio:high"),
        ],
    ])


def calendar_kb(year: int, month: int, month_days: list[list[int]], day_counts: dict[str, int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Пн", callback_data="noop"), InlineKeyboardButton(text="Вт", callback_data="noop"),
         InlineKeyboardButton(text="Ср", callback_data="noop"), InlineKeyboardButton(text="Чт", callback_data="noop"),
         InlineKeyboardButton(text="Пт", callback_data="noop"), InlineKeyboardButton(text="Сб", callback_data="noop"),
         InlineKeyboardButton(text="Вс", callback_data="noop")]
    ]
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            else:
                key = f"{year:04d}-{month:02d}-{day:02d}"
                count = day_counts.get(key, 0)
                label = f"{day}•" if count else str(day)
                row.append(InlineKeyboardButton(text=label, callback_data=f"calday:{key}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"calnav:{year}:{month}:-1"),
        InlineKeyboardButton(text="Сегодня", callback_data="caltoday"),
        InlineKeyboardButton(text="➡️", callback_data=f"calnav:{year}:{month}:1"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
