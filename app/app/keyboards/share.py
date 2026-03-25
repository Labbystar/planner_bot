from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def share_accept_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Принять", callback_data=f"share_accept:{token}")],
            [InlineKeyboardButton(text="Отмена", callback_data="share_cancel")],
        ]
    )
