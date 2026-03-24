from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.reminders import category_edit_kb, priority_edit_kb, snooze_kb
from app.services.reminders import (
    delete_reminder,
    get_reminder,
    mark_done,
    snooze,
    update_category,
    update_priority,
    update_text,
    update_when,
)
from app.services.users import get_user
from app.utils.time import parse_user_time

router = Router()


class EditReminder(StatesGroup):
    text = State()
    when = State()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("done:"))
async def done(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await mark_done(reminder_id)
    await callback.answer("Отмечено как выполнено")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("snzmenu:"))
async def snooze_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer("На сколько отложить?", reply_markup=snooze_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("snz:"))
async def do_snooze(callback: CallbackQuery) -> None:
    _, reminder_id, minutes = callback.data.split(":")
    await snooze(int(reminder_id), int(minutes))
    await callback.answer(f"Отложено на {minutes} мин")


@router.callback_query(F.data.startswith("del:"))
async def do_delete(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await delete_reminder(reminder_id)
    await callback.answer("Удалено")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("edittext:"))
async def edit_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await state.set_state(EditReminder.text)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer("Отправь новый текст задачи.")


@router.message(EditReminder.text)
async def edit_text_apply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    reminder_id = data.get("reminder_id")
    if not reminder_id:
        await state.clear()
        return
    await update_text(reminder_id, message.text)
    await state.clear()
    await message.answer("✅ Текст обновлен.")


@router.callback_query(F.data.startswith("edittime:"))
async def edit_time_start(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await state.set_state(EditReminder.when)
    await state.update_data(reminder_id=reminder_id)
    await callback.answer()
    await callback.message.answer(
        "Укажи новое время. Например:\n"
        "• 2026-03-30 14:45\n"
        "• завтра в 9\n"
        "• через 2 часа"
    )


@router.message(EditReminder.when)
async def edit_time_apply(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    reminder_id = data.get("reminder_id")
    if not reminder_id or not user:
        await state.clear()
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
    await callback.message.answer("Выбери новую категорию:", reply_markup=category_edit_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("editcat:"))
async def edit_category_apply(callback: CallbackQuery) -> None:
    _, reminder_id, category = callback.data.split(":")
    await update_category(int(reminder_id), category)
    await callback.answer("Категория обновлена")


@router.callback_query(F.data.startswith("editpriomenu:"))
async def edit_priority_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer("Выбери новый приоритет:", reply_markup=priority_edit_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("editprio:"))
async def edit_priority_apply(callback: CallbackQuery) -> None:
    _, reminder_id, priority = callback.data.split(":")
    await update_priority(int(reminder_id), priority)
    await callback.answer("Приоритет обновлен")
