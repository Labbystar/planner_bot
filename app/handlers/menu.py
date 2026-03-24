from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.keyboards.menu import main_menu, more_menu
from app.keyboards.reminders import pager, reminder_actions, settings_kb
from app.services.reminders import get_reminder, list_active_reminders
from app.services.users import get_user
from app.utils.formatting import page_header, reminder_card
from app.utils.time import to_local

router = Router()


@router.message(F.text == "📋 Активные")
async def active(message: Message) -> None:
    await send_reminders_page(message, message.from_user.id, 1)


@router.message(F.text == "📅 Сегодня")
async def today(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    reminders, _ = await list_active_reminders(message.from_user.id, 1, 50)
    lines = ["<b>📅 Сегодня</b>"]
    for r in reminders:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        if dt_local.date() == datetime.now(dt_local.tzinfo).date():
            lines.append(f"• {dt_local.strftime('%H:%M')} — {r['text']}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message) -> None:
    user = await get_user(message.from_user.id)
    await message.answer(
        f"<b>⚙️ Настройки</b>\n\n🌍 {user['timezone_name']}",
        parse_mode="HTML",
        reply_markup=settings_kb(bool(user["quiet_hours_enabled"])),
    )


@router.message(F.text == "🆔 Мой ID")
async def myid(message: Message) -> None:
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@router.message(F.text == "⬅️ Назад")
async def back(message: Message) -> None:
    await message.answer("Главное меню", reply_markup=main_menu())


async def send_reminders_page(target: Message | CallbackQuery, user_id: int, page: int) -> None:
    user = await get_user(user_id)
    reminders, total_pages = await list_active_reminders(user_id, page)
    if not reminders:
        text = "<b>📋 Активные напоминания</b>\nПока пусто."
        if isinstance(target, Message):
            await target.answer(text, parse_mode="HTML")
        else:
            await target.message.edit_text(text, parse_mode="HTML")
            await target.answer()
        return

    header = page_header("📋 Активные напоминания", page, total_pages)
    for idx, reminder in enumerate(reminders):
        dt_local = to_local(datetime.fromisoformat(reminder["scheduled_at_utc"]), user["timezone_name"])
        text = (header + "\n\n" if idx == 0 else "") + reminder_card(reminder, dt_local)
        if isinstance(target, Message):
            await target.answer(text, parse_mode="HTML", reply_markup=reminder_actions(reminder["id"]))
        else:
            await target.message.answer(text, parse_mode="HTML", reply_markup=reminder_actions(reminder["id"]))
    pg = pager(page, total_pages)
    if pg:
        if isinstance(target, Message):
            await target.answer("Навигация", reply_markup=pg)
        else:
            await target.message.answer("Навигация", reply_markup=pg)
            await target.answer()


@router.callback_query(F.data.startswith("page:"))
async def switch_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    await send_reminders_page(callback, callback.from_user.id, page)
