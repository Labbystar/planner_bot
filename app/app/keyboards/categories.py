from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💼 Работа", callback_data="category:work")],
            [InlineKeyboardButton(text="🏠 Личное", callback_data="category:personal")],
            [InlineKeyboardButton(text="💰 Финансы", callback_data="category:finance")],
            [InlineKeyboardButton(text="⭐ Важное", callback_data="category:important")],
        ]
    )
