from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать"), KeyboardButton(text="⚡ Быстро")],
            [KeyboardButton(text="📥 Мне поставили"), KeyboardButton(text="📤 Я поставил")],
            [KeyboardButton(text="📋 Активные"), KeyboardButton(text="📅 Сегодня")],
            [KeyboardButton(text="🌤 Завтра"), KeyboardButton(text="🗓 Неделя")],
            [KeyboardButton(text="🗓 Календарь"), KeyboardButton(text="⏳ Просроченные")],
            [KeyboardButton(text="🔎 Поиск"), KeyboardButton(text="📤 Экспорт CSV")],
            [KeyboardButton(text="📥 Импорт CSV"), KeyboardButton(text="📤 Экспорт Excel")],
            [KeyboardButton(text="📥 Импорт Excel"), KeyboardButton(text="📄 Word-отчёт")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🆔 Мой ID")],
            [KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )

main_menu_kb = main_menu
