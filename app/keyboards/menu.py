from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


MAIN_MENU_TEXTS = {
    "create": "➕ Создать напоминание",
    "list": "📋 Мои напоминания",
    "settings": "⚙️ Настройки",
    "share": "🔗 Мои ссылки",
    "myid": "🆔 Мой ID",
    "cancel": "❌ Отмена",
}


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_TEXTS["create"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["list"]), KeyboardButton(text=MAIN_MENU_TEXTS["myid"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["settings"]), KeyboardButton(text=MAIN_MENU_TEXTS["share"])],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_TEXTS["cancel"]) ]],
        resize_keyboard=True,
        input_field_placeholder="Можно отменить создание",
    )


def reminder_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Один раз", callback_data="create_kind:once")],
            [InlineKeyboardButton(text="Каждый день", callback_data="create_kind:daily")],
            [InlineKeyboardButton(text="Каждую неделю", callback_data="create_kind:weekly")],
        ]
    )


def reminder_actions_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"reminder_delete:{reminder_id}")],
            [
                InlineKeyboardButton(text="📄 Ссылка-копия", callback_data=f"reminder_sharecopy:{reminder_id}"),
                InlineKeyboardButton(text="👥 Ссылка-подписка", callback_data=f"reminder_sharerecipient:{reminder_id}"),
            ],
        ]
    )


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Показать мое время", callback_data="settings:time")],
            [InlineKeyboardButton(text="Показать таймзону", callback_data="settings:timezone")],
            [
                InlineKeyboardButton(text="Новосибирск", callback_data="settings:settz:Asia/Novosibirsk"),
                InlineKeyboardButton(text="Москва", callback_data="settings:settz:Europe/Moscow"),
            ],
        ]
    )

