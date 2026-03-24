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
