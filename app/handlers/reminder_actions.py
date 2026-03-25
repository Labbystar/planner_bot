from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.reminders import category_edit_kb, priority_edit_kb, snooze_kb
from app.services.reminders import (
    count_attachments,
    confirm_done,
    delete_reminder,
    get_reminder,
    list_attachments,
    mark_done,
    mark_in_progress,
    set_assignee_comment,
    snooze,
    toggle_assignee_edit,
    return_to_work,
    update_category,
    update_priority,
    update_text,
    update_when,
)
from app.services.users import get_user
from app.utils.formatting import assignee_feedback_notification, owner_confirmation_notification, owner_status_notification, user_label
from app.utils.time import parse_user_time

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


async def _notify_owner(callback_or_msg, reminder: dict, actor: dict, action_text: str, comment: str | None = None):
    owner_id = reminder.get('owner_user_id')
    actor_id = actor.get('user_id') if actor else None
    if not owner_id or owner_id == actor_id:
        return
    try:
        await callback_or_msg.bot.send_message(owner_id, owner_status_notification(reminder, user_label(actor, actor_id), action_text, comment), parse_mode='HTML')
    except Exception:
        pass


async def _send_attachments(target_message: Message, reminder_id: int) -> None:
    attachments = await list_attachments(reminder_id)
    if not attachments:
        await target_message.answer('📎 У задачи пока нет вложений.')
        return
    await target_message.answer(f'📎 Вложений: {len(attachments)}')
    bot = target_message.bot
    uid = target_message.chat.id
    for att in attachments:
        atype = att['attachment_type']
        if atype == 'photo' and att.get('telegram_file_id'):
            await bot.send_photo(uid, att['telegram_file_id'])
        elif atype == 'document' and att.get('telegram_file_id'):
            await bot.send_document(uid, att['telegram_file_id'])
        elif atype == 'voice' and att.get('telegram_file_id'):
            await bot.send_voice(uid, att['telegram_file_id'])
        elif atype == 'audio' and att.get('telegram_file_id'):
            await bot.send_audio(uid, att['telegram_file_id'])
        elif atype == 'text' and att.get('text_value'):
            await bot.send_message(uid, f"📝 {att['text_value']}")
        elif atype == 'link' and att.get('url_value'):
            await bot.send_message(uid, f"🔗 {att['url_value']}")


@router.callback_query(F.data == 'noop')
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith('atts:'))
async def attachments_open(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await _send_attachments(callback.message, reminder_id)
    await callback.answer()


@router.callback_query(F.data.startswith('accept:'))
async def accept_task(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await mark_in_progress(reminder_id)
    reminder = await get_reminder(reminder_id)
    await _notify_owner(callback, reminder, viewer, 'Принято в работу')
    await callback.answer('Задача принята в работу')


@router.callback_query(F.data.startswith('done:'))
async def done(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not reminder or not viewer or not _can_act(reminder, viewer):
        await callback.answer('Нет доступа', show_alert=True)
        return
    if reminder.get('owner_user_id') == viewer['user_id']:
        await confirm_done(reminder_id)
        reminder = await get_reminder(reminder_id)
        await callback.answer('Задача подтверждена')
        await callback.message.edit_reply_markup(reply_markup=None)
        return
    await mark_done(reminder_id)
    reminder = await get_reminder(reminder_id)
    owner_id = reminder.get('owner_user_id')
    if owner_id and owner_id != viewer['user_id']:
        from app.keyboards.reminders import owner_confirmation_actions
        try:
            await callback.bot.send_message(
                owner_id,
                owner_confirmation_notification(reminder, user_label(viewer, viewer.get('user_id'))),
                parse_mode='HTML',
                reply_markup=owner_confirmation_actions(reminder_id, bool(reminder.get('assignee_can_edit'))),
            )
        except Exception:
            pass
    await callback.answer('Отмечено как выполнено. Ожидается подтверждение постановщика')
    await callback.message.edit_reply_markup(reply_markup=None)




@router.callback_query(F.data.startswith('confirmdone:'))
async def confirm_done_handler(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not reminder or not viewer or not (viewer.get('role') in {'admin', 'manager'} or reminder.get('owner_user_id') == viewer['user_id']):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await confirm_done(reminder_id)
    reminder = await get_reminder(reminder_id)
    assignee_id = reminder.get('assigned_user_id')
    if assignee_id and assignee_id != viewer['user_id']:
        try:
            await callback.bot.send_message(assignee_id, assignee_feedback_notification(reminder, '🔵 Выполнение подтверждено'), parse_mode='HTML')
        except Exception:
            pass
    await callback.answer('Выполнение подтверждено')
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith('returnwork:'))
async def return_work_handler(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not reminder or not viewer or not (viewer.get('role') in {'admin', 'manager'} or reminder.get('owner_user_id') == viewer['user_id']):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await return_to_work(reminder_id)
    reminder = await get_reminder(reminder_id)
    assignee_id = reminder.get('assigned_user_id')
    if assignee_id and assignee_id != viewer['user_id']:
        try:
            await callback.bot.send_message(assignee_id, assignee_feedback_notification(reminder, '🔁 Задача возвращена в работу'), parse_mode='HTML')
        except Exception:
            pass
    await callback.answer('Задача возвращена в работу')
    await callback.message.edit_reply_markup(reply_markup=None)

@router.callback_query(F.data.startswith('comment:'))
async def comment_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await state.set_state(EditReminder.comment)
    await state.update_data(reminder_id=reminder_id)
    await callback.message.answer('Напиши комментарий по задаче одним сообщением.')
    await callback.answer()


@router.message(EditReminder.comment)
async def comment_apply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    if not reminder_id:
        await state.clear(); return
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(message.from_user.id)
    if not _can_act(reminder, viewer):
        await state.clear(); return
    await set_assignee_comment(reminder_id, message.text)
    reminder = await get_reminder(reminder_id)
    await _notify_owner(message, reminder, viewer, 'Комментарий исполнителя', message.text)
    await state.clear()
    await message.answer('✅ Комментарий сохранён.')


@router.callback_query(F.data.startswith('snzmenu:'))
async def snooze_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await callback.message.answer('На сколько отложить?', reply_markup=snooze_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith('snz:'))
async def do_snooze(callback: CallbackQuery) -> None:
    _, reminder_id, minutes = callback.data.split(':')
    reminder = await get_reminder(int(reminder_id))
    viewer = await get_user(callback.from_user.id)
    if not _can_act(reminder, viewer):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await snooze(int(reminder_id), int(minutes))
    reminder = await get_reminder(int(reminder_id))
    await _notify_owner(callback, reminder, viewer, f'Отложено на {minutes} мин')
    await callback.answer(f'Отложено на {minutes} мин')


@router.callback_query(F.data.startswith('del:'))
async def do_delete(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer('Только постановщик или админ может удалить задачу', show_alert=True)
        return
    await delete_reminder(reminder_id)
    await callback.answer('Удалено')
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith('toggleedit:'))
async def toggle_edit(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not reminder or not viewer or not (viewer.get('role') == 'admin' or reminder.get('owner_user_id') == viewer['user_id']):
        await callback.answer('Нет доступа', show_alert=True)
        return
    await toggle_assignee_edit(reminder_id)
    await callback.answer('Право редактирования переключено')


@router.callback_query(F.data.startswith('edittext:'))
async def edit_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer('Редактирование недоступно', show_alert=True)
        return
    await state.set_state(EditReminder.text)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer('Отправь новый текст задачи.')


@router.message(EditReminder.text)
async def edit_text_apply(message: Message, state: FSMContext) -> None:
    data = await state.get_data(); reminder_id = data.get('reminder_id')
    if not reminder_id:
        await state.clear(); return
    await update_text(reminder_id, message.text)
    await state.clear(); await message.answer('✅ Текст обновлен.')


@router.callback_query(F.data.startswith('edittime:'))
async def edit_time_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer('Редактирование недоступно', show_alert=True)
        return
    await state.set_state(EditReminder.when)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer('Укажи новое время. Например:\n• через час\n• 11:30\n• сегодня в 13:00\n• завтра в 9\n• 25.03.2026 14:45')


@router.message(EditReminder.when)
async def edit_time_apply(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    data = await state.get_data(); reminder_id = data.get('reminder_id')
    if not reminder_id or not user:
        await state.clear(); return
    try:
        dt_local = parse_user_time(message.text, user['timezone_name'])
    except ValueError:
        await message.answer('Не понял дату/время. Попробуй: <code>через час</code>, <code>11:30</code>, <code>сегодня в 13:00</code>, <code>завтра в 9</code> или <code>25.03.2026 14:45</code>', parse_mode='HTML')
        return
    await update_when(reminder_id, dt_local.astimezone(timezone.utc).isoformat())
    await state.clear(); await message.answer(f"✅ Время обновлено: {dt_local.strftime('%d.%m.%Y %H:%M')}")


@router.callback_query(F.data.startswith('editcatmenu:'))
async def edit_category_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer('Редактирование недоступно', show_alert=True)
        return
    await callback.message.answer('Выбери новую категорию:', reply_markup=category_edit_kb(reminder_id)); await callback.answer()


@router.callback_query(F.data.startswith('editcat:'))
async def edit_category_apply(callback: CallbackQuery) -> None:
    _, reminder_id, category = callback.data.split(':')
    await update_category(int(reminder_id), category)
    await callback.answer('Категория обновлена')


@router.callback_query(F.data.startswith('editpriomenu:'))
async def edit_priority_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(':', 1)[1])
    reminder = await get_reminder(reminder_id)
    viewer = await get_user(callback.from_user.id)
    if not _can_edit(reminder, viewer):
        await callback.answer('Редактирование недоступно', show_alert=True)
        return
    await callback.message.answer('Выбери новый приоритет:', reply_markup=priority_edit_kb(reminder_id)); await callback.answer()


@router.callback_query(F.data.startswith('editprio:'))
async def edit_priority_apply(callback: CallbackQuery) -> None:
    _, reminder_id, priority = callback.data.split(':')
    await update_priority(int(reminder_id), priority)
    await callback.answer('Приоритет обновлен')
