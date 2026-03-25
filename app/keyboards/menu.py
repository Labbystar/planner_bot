from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать"), KeyboardButton(text="⚡ Быстро")],
            [KeyboardButton(text="📥 Мне поставили"), KeyboardButton(text="📤 Я поставил")],
            [KeyboardButton(text="📋 Задачи"), KeyboardButton(text="📊 Команда")],
            [KeyboardButton(text="⚙️ Сервис"), KeyboardButton(text="🆔 Мой ID")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def tasks_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Активные"), KeyboardButton(text="📅 Сегодня")],
            [KeyboardButton(text="🌤 Завтра"), KeyboardButton(text="🗓 Неделя")],
            [KeyboardButton(text="🗓 Календарь"), KeyboardButton(text="⏳ Просроченные")],
            [KeyboardButton(text="🔎 Поиск"), KeyboardButton(text="📤 CSV")],
            [KeyboardButton(text="⬅️ Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Раздел: Задачи",
    )


def team_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика по сотрудникам"), KeyboardButton(text="👑 Админка")],
            [KeyboardButton(text="📥 Мне поставили"), KeyboardButton(text="📤 Я поставил")],
            [KeyboardButton(text="⬅️ Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Раздел: Команда",
    )


def service_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🆔 Мой ID")],
            [KeyboardButton(text="⬅️ Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Раздел: Сервис",
    )
