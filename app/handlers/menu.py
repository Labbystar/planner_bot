from __future__ import annotations

import calendar
import csv
import io
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.keyboards.reminders import active_filters_kb, calendar_kb, pager, reminder_actions, settings_kb
from app.services.reminders import (
    create_reminder,
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
from app.utils.time import parse_user_time, to_local

router = Router()


class SearchFlow(StatesGroup):
    query = State()


class CsvImportFlow(StatesGroup):
    wait_file = State()


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


@router.message(F.text == "📤 Экспорт CSV")
async def export_csv(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    rows = await list_all_reminders(message.from_user.id)
    if not rows:
        await message.answer("Пока нечего экспортировать.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "text",
        "note",
        "category",
        "priority",
        "status",
        "owner_user_id",
        "assigned_user_id",
        "scheduled_local",
        "scheduled_utc",
        "created_at_utc",
        "updated_at_utc",
        "completed_at_utc",
    ])
    for r in rows:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        writer.writerow([
            r.get("id", ""),
            r.get("text", ""),
            r.get("note", "") or "",
            r.get("category", "") or "",
            r.get("priority", "") or "",
            r.get("status", "") or "",
            r.get("owner_user_id", ""),
            r.get("assigned_user_id", ""),
            dt_local.strftime("%Y-%m-%d %H:%M"),
            r.get("scheduled_at_utc", "") or "",
            r.get("created_at", "") or "",
            r.get("updated_at", "") or "",
            r.get("completed_at", "") or "",
        ])
    payload = output.getvalue().encode("utf-8-sig")
    filename = f"napomnime_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await message.answer_document(
        BufferedInputFile(payload, filename=filename),
        caption="Готово. Это полный экспорт задач и статусов в CSV.",
    )


@router.message(F.text == "📥 Импорт CSV")
async def import_csv_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CsvImportFlow.wait_file)
    await message.answer(
        "Пришли CSV-файл с задачами.\n\n"
        "Поддерживаемые колонки:\n"
        "• text — обязательно\n"
        "• scheduled_local — обязательно, например 2026-03-30 14:45\n"
        "• note\n"
        "• category = work/personal/finance/important\n"
        "• priority = low/medium/high\n"
        "• assigned_user_id — если нужно назначить другому пользователю\n\n"
        "Если assigned_user_id не указан, задача назначится тебе."
    )


@router.message(CsvImportFlow.wait_file, F.document)
async def import_csv_file(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        return
    if not message.document.file_name.lower().endswith('.csv'):
        await message.answer("Нужен именно CSV-файл.")
        return

    file = await message.bot.get_file(message.document.file_id)
    content = await message.bot.download_file(file.file_path)
    raw = content.read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        await message.answer("Не удалось прочитать CSV. Похоже, в файле нет заголовков колонок.")
        return

    imported = 0
    errors: list[str] = []
    allowed_categories = {"work", "personal", "finance", "important"}
    allowed_priorities = {"low", "medium", "high"}

    for idx, row in enumerate(reader, start=2):
        try:
            reminder_text = (row.get("text") or "").strip()
            if not reminder_text:
                raise ValueError("пустой text")
            when_raw = (row.get("scheduled_local") or "").strip()
            if not when_raw:
                raise ValueError("пустой scheduled_local")
            dt_local = parse_user_time(when_raw, user["timezone_name"])
            category = (row.get("category") or "work").strip().lower() or "work"
            priority = (row.get("priority") or "medium").strip().lower() or "medium"
            if category not in allowed_categories:
                category = "work"
            if priority not in allowed_priorities:
                priority = "medium"
            note = (row.get("note") or "").strip() or None
            assigned_raw = (row.get("assigned_user_id") or "").strip()
            assigned_user_id = message.from_user.id
            if assigned_raw:
                if not assigned_raw.isdigit():
                    raise ValueError("assigned_user_id должен быть числом")
                from app.services.users import get_user as get_user_by_id
                target = await get_user_by_id(int(assigned_raw))
                if not target:
                    raise ValueError("assigned_user_id не найден среди активных пользователей")
                assigned_user_id = int(assigned_raw)

            await create_reminder(
                owner_user_id=message.from_user.id,
                assigned_user_id=assigned_user_id,
                text=reminder_text,
                scheduled_at_utc=dt_local.astimezone(timezone.utc).isoformat(),
                category=category,
                priority=priority,
                note=note,
            )
            imported += 1
        except Exception as e:
            errors.append(f"Строка {idx}: {e}")

    await state.clear()
    summary = [f"Импорт завершён.\n\n✅ Импортировано: {imported}"]
    if errors:
        preview = "\n".join(errors[:10])
        summary.append(f"\n⚠️ Ошибок: {len(errors)}\n{preview}")
    await message.answer("".join(summary))


@router.message(CsvImportFlow.wait_file)
async def import_csv_wrong_payload(message: Message) -> None:
    await message.answer("Пришли CSV-файл документом. Чтобы выйти из режима импорта, нажми /start или выбери другой раздел.")


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
    start_local = datetime.fromisoformat(day_key + "T00:00:00").replace(tzinfo=to_local(datetime.now(timezone.utc), user["timezone_name"]).tzinfo)
    end_local = start_local + timedelta(days=1)
    rows = await list_by_time_window(callback.from_user.id, start_local.astimezone(timezone.utc).isoformat(), end_local.astimezone(timezone.utc).isoformat())
    if not rows:
        await callback.answer("На этот день задач нет", show_alert=True)
        return
    lines = [f"<b>🗓 {start_local.strftime('%d.%m.%Y')}</b>"]
    for r in rows[:20]:
        dt_local = to_local(datetime.fromisoformat(r["scheduled_at_utc"]), user["timezone_name"])
        lines.append(list_line(r, dt_local))
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("page:"))
async def page_change(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    await send_reminders_page(callback, callback.from_user.id, page)


@router.callback_query(F.data == "flt:all")
async def filter_all(callback: CallbackQuery) -> None:
    await send_reminders_page(callback, callback.from_user.id, 1)


@router.callback_query(F.data.startswith("flt:"))
async def filter_category(callback: CallbackQuery) -> None:
    category = callback.data.split(":", 1)[1]
    await send_reminders_page(callback, callback.from_user.id, 1, category=category)


@router.callback_query(F.data.startswith("fltprio:"))
async def filter_priority(callback: CallbackQuery) -> None:
    priority = callback.data.split(":", 1)[1]
    await send_reminders_page(callback, callback.from_user.id, 1, priority=priority)
