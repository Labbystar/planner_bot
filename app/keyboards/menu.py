from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать"), KeyboardButton(text="⚡ Быстро")],
            [KeyboardButton(text="📋 Активные"), KeyboardButton(text="📅 Сегодня")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🆔 Мой ID")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def more_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📜 История"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🔎 Поиск"), KeyboardButton(text="🔗 Ссылки")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )
