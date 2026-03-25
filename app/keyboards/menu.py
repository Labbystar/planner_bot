
# Добавь кнопку в главное меню

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать")],
            [KeyboardButton(text="📊 Статистика по сотрудникам")],
            [KeyboardButton(text="👑 Админка")],
        ],
        resize_keyboard=True
    )
