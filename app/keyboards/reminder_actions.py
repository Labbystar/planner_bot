from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def reminder_actions_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнено", callback_data=f"reminder_done:{reminder_id}"),
                InlineKeyboardButton(text="👁 Подтвердить", callback_data=f"reminder_ack:{reminder_id}"),
            ],
            [
                InlineKeyboardButton(text="⏰ Отложить", callback_data=f"reminder_snooze_menu:{reminder_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"reminder_delete:{reminder_id}"),
            ],
            [
                InlineKeyboardButton(text="🧩 В шаблоны", callback_data=f"reminder_template:{reminder_id}"),
            ],
            [
                InlineKeyboardButton(text="📄 Ссылка-копия", callback_data=f"reminder_sharecopy:{reminder_id}"),
                InlineKeyboardButton(text="👥 Ссылка-подписка", callback_data=f"reminder_sharerecipient:{reminder_id}"),
            ],
        ]
    )
