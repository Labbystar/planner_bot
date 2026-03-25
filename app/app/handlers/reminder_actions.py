from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.reminders import category_edit_kb, priority_edit_kb, snooze_kb
from app.services.reminders import delete_reminder, get_reminder, mark_done, snooze, toggle_assignee_edit, update_assignee_comment, update_category, update_priority, update_text, update_when
from app.services.users import get_user
from app.utils.formatting import user_label
from app.utils.time import parse_user_time, to_local

router = Router()


class EditReminder(StatesGroup):
    text = State()
    when = State()
    comment = State()


def _can_edit(reminder: dict | None, viewer: dict | None) -> bool:
    if not reminder or not viewer:
        return False
    if reminder.get('owner_user_id') == viewer['user_id']:
        return True
    if viewer.get('role') in {'admin', 'manager'}:
        return True
    return reminder.get('assigned_user_id') == viewer['user_id'] and bool(reminder.get('assignee_can_edit'))


def _can_act(reminder: dict | None, viewer: dict | None) -> bool:
    if not reminder or not viewer:
        return False
    return viewer['user_id'] in {reminder.get('owner_user_id'), reminder.get('assigned_user_id')} or viewer.get('role') in {'admin', 'manager'}


async def _notify_owner(bot, reminder: dict | None, actor_user_id: int, status_label: str, extra: str | None = None) -> None:
    if not reminder:
        return
    owner_id = reminder.get('owner_user_id')
    if not owner_id or owner_id == actor_user_id:
        return
    owner = await get_user(owner_id)
    actor = await get_user(actor_user_id)
    if not owner:
        return
    actor_name = user_label(actor, actor_user_id)
    lines = [
        "📣 Обновление по задаче",
        "",
        f"📌 {reminder.get('text', '')}",
        f"👤 {actor_name}",
        f"{status_label}",
    ]
    if extra:
        lines.append(extra)
    try:
        await bot.send_message(owner_id, "\n".join(lines))
    except Exception:
        pass


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("accept:"))
async def accept_task(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _notify_owner(callback.bot, reminder, callback.from_user.id, "👁 Статус: Принято")
    await callback.answer("Задача принята")


@router.callback_query(F.data.startswith("done:"))
async def done(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await mark_done(reminder_id)
    updated = await get_reminder(reminder_id)
    await _notify_owner(callback.bot, updated, callback.from_user.id, "✅ Статус: Выполнено")
    await callback.answer("Отмечено как выполнено")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("snzmenu:"))
async def snooze_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.answer("На сколько отложить?", reply_markup=snooze_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("snz:"))
async def do_snooze(callback: CallbackQuery) -> None:
    _, reminder_id, minutes = callback.data.split(":")
    reminder = await get_reminder(int(reminder_id))
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await snooze(int(reminder_id), int(minutes))
    updated = await get_reminder(int(reminder_id))
    await _notify_owner(callback.bot, updated, callback.from_user.id, f"⏰ Статус: Отложено на {minutes} мин")
    await callback.answer(f"Отложено на {minutes} мин")


@router.callback_query(F.data.startswith("comment:"))
async def comment_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not reminder or not viewer or callback.from_user.id != reminder.get('assigned_user_id'):
        await callback.answer("Только исполнитель может добавить комментарий", show_alert=True)
        return
    await state.set_state(EditReminder.comment)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer("Напиши комментарий по задаче.")


@router.message(EditReminder.comment)
async def comment_apply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    reminder = await get_reminder(reminder_id) if reminder_id else None
    if not reminder or message.from_user.id != reminder.get('assigned_user_id'):
        await state.clear()
        await message.answer("Комментарий недоступен")
        return
    comment = (message.text or '').strip()
    if not comment:
        await message.answer("Комментарий не должен быть пустым")
        return
    await update_assignee_comment(reminder_id, comment)
    updated = await get_reminder(reminder_id)
    await _notify_owner(message.bot, updated, message.from_user.id, "💬 Исполнитель оставил комментарий", f"📝 {comment}")
    await state.clear()
    await message.answer("✅ Комментарий сохранён")


@router.callback_query(F.data.startswith("del:"))
async def do_delete(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Только постановщик или админ может удалить задачу", show_alert=True)
        return
    await delete_reminder(reminder_id)
    await callback.answer("Удалено")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("toggleedit:"))
async def toggle_edit(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not reminder or not viewer or not (viewer.get('role') == 'admin' or reminder.get('owner_user_id') == viewer['user_id']):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await toggle_assignee_edit(reminder_id)
    await callback.answer("Право редактирования переключено")


@router.callback_query(F.data.startswith("edittext:"))
async def edit_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Редактирование недоступно", show_alert=True)
        return
    await state.set_state(EditReminder.text)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer("Отправь новый текст задачи.")


@router.message(EditReminder.text)
async def edit_text_apply(message: Message, state: FSMContext) -> None:
    reminder_id = (await state.get_data()).get("reminder_id")
    reminder = await get_reminder(reminder_id) if reminder_id else None
    viewer = await get_user(message.from_user.id)
    if not reminder_id or not _can_edit(reminder, viewer):
        await state.clear()
        await message.answer("Редактирование недоступно")
        return
    await update_text(reminder_id, message.text)
    await state.clear()
    await message.answer("✅ Текст обновлен.")


@router.callback_query(F.data.startswith("edittime:"))
async def edit_time_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Редактирование недоступно", show_alert=True)
        return
    await state.set_state(EditReminder.when)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer("Укажи новое время. Например:\n• 2026-03-30 14:45\n• завтра в 9\n• через 2 часа")


@router.message(EditReminder.when)
async def edit_time_apply(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    reminder_id = (await state.get_data()).get("reminder_id")
    reminder = await get_reminder(reminder_id) if reminder_id else None
    if not reminder_id or not user or not _can_edit(reminder, user):
        await state.clear()
        await message.answer("Редактирование недоступно")
        return
    try:
        dt_local = parse_user_time(message.text, user["timezone_name"])
    except ValueError:
        await message.answer("Не понял дату/время. Попробуй: <code>завтра в 9</code> или <code>2026-03-30 14:45</code>", parse_mode="HTML")
        return
    await update_when(reminder_id, dt_local.astimezone(timezone.utc).isoformat())
    await state.clear()
    await message.answer(f"✅ Время обновлено: {dt_local.strftime('%d.%m.%Y %H:%M')}")


@router.callback_query(F.data.startswith("editcatmenu:"))
async def edit_category_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Редактирование недоступно", show_alert=True)
        return
    await callback.message.answer("Выбери новую категорию:", reply_markup=category_edit_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("editcat:"))
async def edit_category_apply(callback: CallbackQuery) -> None:
    _, reminder_id, category = callback.data.split(":")
    reminder = await get_reminder(int(reminder_id))
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Редактирование недоступно", show_alert=True)
        return
    await update_category(int(reminder_id), category)
    await callback.answer("Категория обновлена")


@router.callback_query(F.data.startswith("editpriomenu:"))
async def edit_priority_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Редактирование недоступно", show_alert=True)
        return
    await callback.message.answer("Выбери новый приоритет:", reply_markup=priority_edit_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("editprio:"))
async def edit_priority_apply(callback: CallbackQuery) -> None:
    _, reminder_id, priority = callback.data.split(":")
    reminder = await get_reminder(int(reminder_id))
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer("Редактирование недоступно", show_alert=True)
        return
    await update_priority(int(reminder_id), priority)
    await callback.answer("Приоритет обновлен")
