from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.context import AppContext
from app.keyboards.group_picker import group_members_picker_kb, group_picker_kb, template_list_kb
from app.keyboards.menu import MAIN_MENU_TEXTS, cancel_kb, groups_menu_kb, main_menu_kb, templates_menu_kb
from app.states.reminder_flow import GroupFlow, ReminderFlow, TemplateFlow

router = Router()


@router.message(F.text == MAIN_MENU_TEXTS["groups"])
async def groups_entry(message: Message):
    await message.answer("Группы получателей", reply_markup=groups_menu_kb())


@router.message(F.text == MAIN_MENU_TEXTS["templates"])
async def templates_entry(message: Message):
    await message.answer("Шаблоны напоминаний", reply_markup=templates_menu_kb())


@router.message(F.text == MAIN_MENU_TEXTS["role"])
@router.message(Command("role"))
async def role_info(message: Message, app: AppContext):
    user = await app.users_repo.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала /start")
        return
    await message.answer(
        f"Твоя роль: <b>{user.role}</b>\n\n"
        "Доступные роли: user, manager, admin\n"
        "Команда для админа: /setrole USER_ID admin|manager|user"
    )


@router.message(Command("setrole"))
async def setrole(message: Message, command: CommandObject, app: AppContext):
    if not command.args:
        await message.answer("Формат: /setrole USER_ID admin|manager|user")
        return
    parts = command.args.split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Формат: /setrole USER_ID admin|manager|user")
        return
    ok = await app.users_repo.set_user_role(message.from_user.id, int(parts[0]), parts[1].strip().lower())
    await message.answer("Роль обновлена." if ok else "Не удалось изменить роль. Нужна роль admin или неверные данные.")


@router.callback_query(F.data == "group_create")
async def group_create_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(GroupFlow.waiting_for_name)
    await callback.message.answer("Название новой группы:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(GroupFlow.waiting_for_name)
async def group_name(message: Message, state: FSMContext, app: AppContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не должно быть пустым")
        return
    await state.update_data(group_name=name, group_selected=[message.from_user.id], group_page=0)
    await state.set_state(GroupFlow.waiting_for_members)
    users = await app.users_repo.list_users()
    await message.answer("Выбери участников группы:", reply_markup=group_members_picker_kb(users, [message.from_user.id], 0))


@router.callback_query(GroupFlow.waiting_for_members, F.data.startswith("group_member_toggle:"))
async def group_member_toggle(callback: CallbackQuery, state: FSMContext, app: AppContext):
    _, uid_raw, page_raw = callback.data.split(":")
    uid, page = int(uid_raw), int(page_raw)
    data = await state.get_data()
    selected = set(data.get("group_selected", []))
    if uid in selected:
        selected.remove(uid)
    else:
        selected.add(uid)
    await state.update_data(group_selected=list(selected), group_page=page)
    users = await app.users_repo.list_users()
    await callback.message.edit_reply_markup(reply_markup=group_members_picker_kb(users, list(selected), page))
    await callback.answer()


@router.callback_query(GroupFlow.waiting_for_members, F.data.startswith("group_member_page:"))
async def group_member_page(callback: CallbackQuery, state: FSMContext, app: AppContext):
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    users = await app.users_repo.list_users()
    await state.update_data(group_page=page)
    await callback.message.edit_reply_markup(reply_markup=group_members_picker_kb(users, data.get("group_selected", []), page))
    await callback.answer()


@router.callback_query(GroupFlow.waiting_for_members, F.data == "group_member_done")
async def group_member_done(callback: CallbackQuery, state: FSMContext, app: AppContext):
    data = await state.get_data()
    selected = list(dict.fromkeys(data.get("group_selected", [])))
    if not selected:
        await callback.answer("Выбери хотя бы одного участника", show_alert=True)
        return
    try:
        gid = await app.groups_repo.create_group(callback.from_user.id, data["group_name"], selected)
        await callback.message.answer(
            f"Группа создана. ID: {gid}\nНазвание: {data['group_name']}\nУчастников: {len(selected)}",
            reply_markup=main_menu_kb(),
        )
    except Exception:
        await callback.message.answer("Не удалось создать группу. Возможно, такое имя уже есть.", reply_markup=main_menu_kb())
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "group_list")
async def group_list(callback: CallbackQuery, app: AppContext):
    groups = await app.groups_repo.list_groups(callback.from_user.id)
    if not groups:
        await callback.message.answer("Групп пока нет.")
    else:
        for g in groups:
            members = await app.groups_repo.get_group_members(g.id)
            await callback.message.answer(
                f"<b>{g.name}</b>\nID: {g.id}\nУчастников: {len(members)}",
                reply_markup=group_picker_kb([g], flow_prefix="group_delete_menu"),
            )
    await callback.answer()


@router.callback_query(F.data.startswith("group_delete_menu:"))
async def group_delete(callback: CallbackQuery, app: AppContext):
    gid = int(callback.data.split(":", 1)[1])
    ok = await app.groups_repo.delete_group(callback.from_user.id, gid)
    await callback.message.answer("Группа удалена." if ok else "Не удалось удалить группу.")
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data == "recipient_group_pick")
async def recipient_group_pick(callback: CallbackQuery, app: AppContext):
    groups = await app.groups_repo.list_groups(callback.from_user.id)
    await callback.message.answer("Выбери группу для импорта получателей:", reply_markup=group_picker_kb(groups))
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data.startswith("group_import:"))
async def recipient_group_import(callback: CallbackQuery, state: FSMContext, app: AppContext):
    gid = int(callback.data.split(":", 1)[1])
    members = await app.groups_repo.get_group_members(gid)
    data = await state.get_data()
    selected = set(data.get("selected_recipients", []))
    selected.update(members)
    await state.update_data(selected_recipients=list(selected))
    users = await app.users_repo.list_users()
    page = int(data.get("recipient_page", 0) or 0)
    from app.keyboards.recipient_picker import recipient_picker_kb

    await callback.message.answer("Получатели из группы добавлены.", reply_markup=recipient_picker_kb(users, list(selected), page))
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data == "group_picker_back")
async def group_picker_back(callback: CallbackQuery, state: FSMContext, app: AppContext):
    from app.handlers.menu import _send_recipient_picker

    await _send_recipient_picker(callback.message, state, app, "Вернулись к выбору получателей.")
    await callback.answer()


@router.callback_query(F.data == "template_list")
async def template_list(callback: CallbackQuery, app: AppContext):
    templates = await app.templates_repo.list_templates(callback.from_user.id)
    await callback.message.answer("Мои шаблоны:", reply_markup=template_list_kb(templates))
    await callback.answer()


@router.callback_query(F.data.startswith("reminder_template:"))
async def reminder_template_save_start(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.set_state(TemplateFlow.waiting_for_name)
    await state.update_data(template_from_reminder_id=reminder_id)
    await callback.message.answer("Название шаблона:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(TemplateFlow.waiting_for_name)
async def template_name(message: Message, state: FSMContext, app: AppContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не должно быть пустым")
        return
    data = await state.get_data()
    reminder = await app.reminders_repo.get_reminder(int(data["template_from_reminder_id"]))
    if not reminder:
        await state.clear()
        await message.answer("Напоминание не найдено", reply_markup=main_menu_kb())
        return
    try:
        tid = await app.templates_repo.create_template(
            owner_user_id=message.from_user.id,
            name=name,
            text=reminder.text,
            kind=reminder.kind,
            category=reminder.category,
            priority=reminder.priority,
            pre_remind_minutes=reminder.pre_remind_minutes,
            weekday=reminder.weekday,
            local_time=reminder.local_time,
            interval_hours=reminder.interval_hours,
        )
        await message.answer(f"Шаблон сохранён. ID: {tid}", reply_markup=main_menu_kb())
    except Exception:
        await message.answer("Не удалось сохранить шаблон. Возможно, такое имя уже есть.", reply_markup=main_menu_kb())
    await state.clear()


@router.callback_query(F.data.startswith("template_delete:"))
async def template_delete(callback: CallbackQuery, app: AppContext):
    tid = int(callback.data.split(":", 1)[1])
    ok = await app.templates_repo.delete_template(callback.from_user.id, tid)
    await callback.message.answer("Шаблон удалён." if ok else "Не удалось удалить шаблон.")
    await callback.answer()


@router.callback_query(F.data.startswith("template_use:"))
async def template_use(callback: CallbackQuery, state: FSMContext, app: AppContext):
    tid = int(callback.data.split(":", 1)[1])
    template = await app.templates_repo.get_template(tid)
    if not template or template.owner_user_id != callback.from_user.id:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    creator = await app.users_repo.get_user(callback.from_user.id)
    default_selected = [creator.user_id] if creator else []
    await state.clear()
    await state.update_data(
        kind=template.kind,
        text=template.text,
        category=template.category,
        priority=template.priority,
        pre_remind_minutes=template.pre_remind_minutes,
        selected_recipients=default_selected,
        recipient_page=0,
        weekday=template.weekday,
        time_part=template.local_time,
        interval_hours=template.interval_hours,
    )
    await state.set_state(ReminderFlow.waiting_for_recipients)
    from app.handlers.menu import _send_recipient_picker

    await _send_recipient_picker(callback.message, state, app, f"Шаблон «{template.name}» загружен. Выбери получателей.")
    await callback.answer()
