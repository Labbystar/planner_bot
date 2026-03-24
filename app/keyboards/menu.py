from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU_TEXTS = {
    "create": "➕ Создать напоминание",
    "list": "📋 Мои напоминания",
    "history": "📜 История",
    "settings": "⚙️ Настройки",
    "share": "🔗 Мои ссылки",
    "myid": "🆔 Мой ID",
    "stats": "📊 Статистика",
    "groups": "👥 Группы",
    "templates": "🧩 Шаблоны",
    "role": "🛡 Роль",
    "cancel": "❌ Отмена",
}


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_TEXTS["create"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["list"]), KeyboardButton(text=MAIN_MENU_TEXTS["history"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["settings"]), KeyboardButton(text=MAIN_MENU_TEXTS["stats"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["groups"]), KeyboardButton(text=MAIN_MENU_TEXTS["templates"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["share"]), KeyboardButton(text=MAIN_MENU_TEXTS["role"])],
            [KeyboardButton(text=MAIN_MENU_TEXTS["myid"])],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_TEXTS["cancel"])]],
        resize_keyboard=True,
        input_field_placeholder="Можно отменить создание",
    )


def reminder_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Один раз", callback_data="create_kind:once")],
            [InlineKeyboardButton(text="Каждый день", callback_data="create_kind:daily")],
            [InlineKeyboardButton(text="Каждую неделю", callback_data="create_kind:weekly")],
            [InlineKeyboardButton(text="Каждые X часов", callback_data="create_kind:interval")],
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
            [
                InlineKeyboardButton(text="Тихие часы: выкл", callback_data="settings:quiet:off"),
                InlineKeyboardButton(text="23:00–08:00", callback_data="settings:quiet:23-08"),
            ],
            [
                InlineKeyboardButton(text="Рабочие дни: Пн–Пт", callback_data="settings:wd:weekdays"),
                InlineKeyboardButton(text="Все дни", callback_data="settings:wd:all"),
            ],
        ]
    )


def groups_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать группу", callback_data="group_create")],
        [InlineKeyboardButton(text="📋 Мои группы", callback_data="group_list")],
    ])


def templates_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Мои шаблоны", callback_data="template_list")],
    ])
