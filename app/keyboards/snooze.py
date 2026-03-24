from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def snooze_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+5 мин", callback_data=f"reminder_snooze:{reminder_id}:5"),
                InlineKeyboardButton(text="+15 мин", callback_data=f"reminder_snooze:{reminder_id}:15"),
            ],
            [
                InlineKeyboardButton(text="+1 час", callback_data=f"reminder_snooze:{reminder_id}:60"),
                InlineKeyboardButton(text="Завтра 09:00", callback_data=f"reminder_snooze:{reminder_id}:tomorrow0900"),
            ],
        ]
    )
