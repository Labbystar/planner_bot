from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def pre_remind_kb(kind: str) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="Без предуведомления", callback_data="pre:0")]]
    buttons.append([
        InlineKeyboardButton(text="За 10 минут", callback_data="pre:10"),
        InlineKeyboardButton(text="За 1 час", callback_data="pre:60"),
    ])
    if kind == "once":
        buttons.append([InlineKeyboardButton(text="За 1 день", callback_data="pre:1440")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
