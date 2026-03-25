from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def reminder_actions_kb(reminder_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁", callback_data=f"read_{reminder_id}"),
            InlineKeyboardButton(text="✅", callback_data=f"done_{reminder_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"fail_{reminder_id}"),
            InlineKeyboardButton(text="⏰", callback_data=f"snooze_{reminder_id}")
        ]
    ])
