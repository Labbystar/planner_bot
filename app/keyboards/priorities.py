from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def priorities_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Низкий", callback_data="priority:low")],
            [InlineKeyboardButton(text="🟡 Средний", callback_data="priority:medium")],
            [InlineKeyboardButton(text="🔴 Высокий", callback_data="priority:high")],
        ]
    )
