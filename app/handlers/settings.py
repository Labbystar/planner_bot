from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.keyboards.reminders import settings_kb
from app.services.users import get_user, set_timezone, toggle_quiet_hours
from app.utils.time import to_local

router = Router()


@router.callback_query(F.data == "sett:time")
async def show_time(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    now_local = to_local(datetime.utcnow().astimezone(), user["timezone_name"])
    await callback.answer()
    await callback.message.answer(f"🕓 Сейчас у тебя: <b>{now_local.strftime('%d.%m.%Y %H:%M')}</b>", parse_mode="HTML")


@router.callback_query(F.data == "sett:tz")
async def show_tz(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(f"🌍 Текущая таймзона: <b>{user['timezone_name']}</b>", parse_mode="HTML")


@router.callback_query(F.data.startswith("tz:"))
async def set_tz(callback: CallbackQuery) -> None:
    tz_name = callback.data.split(":", 1)[1]
    await set_timezone(callback.from_user.id, tz_name)
    user = await get_user(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=settings_kb(bool(user["quiet_hours_enabled"])))
    await callback.answer(f"Таймзона: {tz_name}")


@router.callback_query(F.data == "sett:quiet")
async def quiet(callback: CallbackQuery) -> None:
    user = await toggle_quiet_hours(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=settings_kb(bool(user["quiet_hours_enabled"])))
    await callback.answer("Тихие часы обновлены")
