from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def group_picker_kb(groups, flow_prefix: str = "group_import") -> InlineKeyboardMarkup:
    rows = []
    for g in groups:
        rows.append([InlineKeyboardButton(text=g.name, callback_data=f"{flow_prefix}:{g.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="group_picker_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="Нет групп", callback_data="group_picker_back")]])


def group_members_picker_kb(users, selected_ids: list[int], page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    selected = set(selected_ids)
    start = page * per_page
    chunk = users[start:start+per_page]
    rows=[]
    for user in chunk:
        label = f"@{user.username}" if user.username else user.full_name
        prefix = "✅" if user.user_id in selected else "⬜"
        rows.append([InlineKeyboardButton(text=f"{prefix} {label}", callback_data=f"group_member_toggle:{user.user_id}:{page}")])
    nav=[]
    if start>0: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"group_member_page:{page-1}"))
    if start+per_page < len(users): nav.append(InlineKeyboardButton(text="➡️", callback_data=f"group_member_page:{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="✅ Сохранить группу", callback_data="group_member_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_list_kb(templates) -> InlineKeyboardMarkup:
    rows=[]
    for t in templates:
        rows.append([
            InlineKeyboardButton(text=f"▶️ {t.name}", callback_data=f"template_use:{t.id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"template_delete:{t.id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="Шаблонов пока нет", callback_data="template_noop")]])
