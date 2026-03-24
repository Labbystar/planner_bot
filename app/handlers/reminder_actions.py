from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.keyboards.reminders import snooze_kb
from app.services.reminders import delete_reminder, mark_done, snooze

router = Router()


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
