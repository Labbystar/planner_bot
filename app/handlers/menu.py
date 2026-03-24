from __future__ import annotations

import calendar
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.keyboards.reminders import active_filters_kb, calendar_kb, pager, reminder_actions, settings_kb
from app.services.reminders import (
    list_active_reminders,
    list_all_reminders,
    list_by_time_window,
    list_month_counts,
    list_overdue,
    search_reminders,
    stats,
)
from app.services.users import get_user
from app.utils.formatting import (
    CATEGORY_LABELS,
    PRIORITY_LABELS,
    calendar_title,
    list_line,
    page_header,
    reminder_card,
    stats_text,
)
from app.utils.time import to_local

router = Router()


class SearchFlow(StatesGroup):
    query = State()


@router.message(F.text == "📋 Активные")
async def active(message: Message) -> None:
    await message.answer("Фильтр списка:", reply_markup=active_filters_kb())
    await send_reminders_page(message, message.from_user.id, 1)


@router.message(F.text == "📅 Сегодня")
async def today(message: Message) -> None:
    await send_window(message, "📅 Сегодня", 0, 1)


@router.message(F.text == "🌤 Завтра")
async def tomorrow(message: Message) -> None:
    await send_window(message, "🌤 Завтра", 1, 2)


@router.message(F.text == "🗓 Неделя")
async def week(message: Message) -> None:
    await send_window(message, "🗓 Неделя", 0, 7)


@router.message(F.text == "🗓 Календарь")
async def calendar_view(message: Message) -> None:
    now = datetime.now()
    await send_month_calendar(message, message.from_user.id, now.year, now.month)


@router.message(F.text == "⏳ Просроченные")
async def overdue(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    reminders = await list_overdue(message.from_user.id)
    if not reminders:
        await message.answer("<b>⏳ Просроченные</b>\nПока пусто.", parse_mode="HTML")
        return
    lines = ["<b>⏳ Просроченные</b>"]
    for r in reminders[:15]:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        lines.append(list_line(r, dt_local))
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(F.text == "🔎 Поиск")
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchFlow.query)
    await message.answer("Введи слово или часть текста задачи для поиска.")


@router.message(SearchFlow.query)
async def search_run(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    rows = await search_reminders(message.from_user.id, message.text)
    await state.clear()
    if not rows:
        await message.answer("Ничего не нашел.")
        return
    lines = [f"<b>🔎 Поиск: {message.text}</b>"]
    for r in rows:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        lines.append(list_line(r, dt_local))
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📤 CSV")
async def export_csv(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    rows = await list_all_reminders(message.from_user.id)
    if not rows:
        await message.answer("Пока нечего экспортировать.")
        return

    lines = ["id,text,note,category,priority,status,scheduled_local,created_at,updated_at"]
    for r in rows:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        row = [
            str(r["id"]),
            (r.get("text") or "").replace('"', '""'),
            (r.get("note") or "").replace('"', '""'),
            r.get("category") or "",
            r.get("priority") or "",
            r.get("status") or "",
            dt_local.strftime("%Y-%m-%d %H:%M"),
            r.get("created_at") or "",
            r.get("updated_at") or "",
        ]
        lines.append(",".join(f'"{v}"' for v in row))
    payload = "\n".join(lines).encode("utf-8")
    filename = f"napomnime_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await message.answer_document(
        BufferedInputFile(payload, filename=filename),
        caption="Экспорт готов. Время в CSV — в твоей текущей таймзоне.",
    )


@router.message(F.text == "📊 Статистика")
async def stats_view(message: Message) -> None:
    data = await stats(message.from_user.id)
    await message.answer(stats_text(data), parse_mode="HTML")


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


async def send_window(message: Message, title: str, start_days: int, end_days: int) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    now_local = datetime.now(tz=to_local(datetime.now(timezone.utc), user["timezone_name"]).tzinfo)
    start_local = (now_local + timedelta(days=start_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = (now_local + timedelta(days=end_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = await list_by_time_window(message.from_user.id, start_local.astimezone(timezone.utc).isoformat(), end_local.astimezone(timezone.utc).isoformat())
    if not rows:
        await message.answer(f"<b>{title}</b>\nПока пусто.", parse_mode="HTML")
        return
    lines = [f"<b>{title}</b>"]
    for r in rows[:20]:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        lines.append(list_line(r, dt_local))
    await message.answer("\n\n".join(lines), parse_mode="HTML")


async def send_reminders_page(target: Message | CallbackQuery, user_id: int, page: int, category: str | None = None, priority: str | None = None) -> None:
    user = await get_user(user_id)
    reminders, total_pages = await list_active_reminders(user_id, page, category=category, priority=priority)
    subtitle = None
    if category:
        subtitle = f"Фильтр: {category}"
    if priority:
        subtitle = f"Фильтр: приоритет {priority}"
    if not reminders:
        text = "<b>📋 Активные напоминания</b>\nПока пусто."
        if isinstance(target, Message):
            await target.answer(text, parse_mode="HTML")
        else:
            await target.message.answer(text, parse_mode="HTML")
            await target.answer()
        return

    header = page_header("📋 Активные напоминания", page, total_pages, subtitle)
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


async def send_month_calendar(target: Message | CallbackQuery, user_id: int, year: int, month: int) -> None:
    user = await get_user(user_id)
    if not user:
        return
    tz = to_local(datetime.now(timezone.utc), user["timezone_name"]).tzinfo
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    counts = await list_month_counts(user_id, start_local.astimezone(timezone.utc).isoformat(), end_local.astimezone(timezone.utc).isoformat())
    month_days = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    text = calendar_title(year, month) + "\n\n• точка рядом с днем = есть задачи"
    kb = calendar_kb(year, month, month_days, counts)
    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await target.answer()


@router.callback_query(F.data.startswith("calnav:"))
async def calendar_nav(callback: CallbackQuery) -> None:
    _, year, month, shift = callback.data.split(":")
    year = int(year)
    month = int(month)
    shift = int(shift)
    month += shift
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    await send_month_calendar(callback, callback.from_user.id, year, month)


@router.callback_query(F.data == "caltoday")
async def calendar_today(callback: CallbackQuery) -> None:
    now = datetime.now()
    await send_month_calendar(callback, callback.from_user.id, now.year, now.month)


@router.callback_query(F.data.startswith("calday:"))
async def calendar_day(callback: CallbackQuery) -> None:
    day_key = callback.data.split(":", 1)[1]
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    tz = to_local(datetime.now(timezone.utc), user["timezone_name"]).tzinfo
    start_local = datetime.fromisoformat(day_key).replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    rows = await list_by_time_window(callback.from_user.id, start_local.astimezone(timezone.utc).isoformat(), end_local.astimezone(timezone.utc).isoformat())
    if not rows:
        await callback.answer("На этот день задач нет")
        return
    lines = [f"<b>🗓 {start_local.strftime('%d.%m.%Y')}</b>"]
    for r in rows[:20]:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        lines.append(list_line(r, dt_local))
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("page:"))
async def switch_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    await send_reminders_page(callback, callback.from_user.id, page)


@router.callback_query(F.data.startswith("flt:"))
async def filter_active(callback: CallbackQuery) -> None:
    val = callback.data.split(":", 1)[1]
    category = None if val == "all" else val
    await callback.answer("Фильтр обновлен")
    await send_reminders_page(callback, callback.from_user.id, 1, category=category)


@router.callback_query(F.data.startswith("fltprio:"))
async def filter_priority(callback: CallbackQuery) -> None:
    prio = callback.data.split(":", 1)[1]
    await callback.answer("Фильтр обновлен")
    await send_reminders_page(callback, callback.from_user.id, 1, priority=prio)
