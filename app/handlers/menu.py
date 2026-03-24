from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.context import AppContext
from app.keyboards.categories import categories_kb
from app.keyboards.menu import MAIN_MENU_TEXTS, cancel_kb, main_menu_kb, reminder_type_kb, settings_kb
from app.keyboards.pre_remind import pre_remind_kb
from app.keyboards.priorities import priorities_kb
from app.keyboards.recipient_picker import recipient_picker_kb
from app.keyboards.reminder_actions import reminder_actions_kb
from app.keyboards.snooze import snooze_kb
from app.states.reminder_flow import ReminderFlow
from app.utils.parsing import normalize_recipients, parse_flexible_time, parse_smart_datetime
from app.utils.timezones import (
    WEEKDAY_HUMAN_RU,
    current_time_in_timezone,
    fmt_local_time_for_user,
    parse_datetime_local,
    parse_weekday,
    validate_timezone_name,
)

router = Router()

CATEGORY_LABELS = {
    "work": "💼 Работа",
    "personal": "🏠 Личное",
    "finance": "💰 Финансы",
    "important": "⭐ Важное",
}

PRIORITY_LABELS = {
    "low": "🟢 Низкий",
    "medium": "🟡 Средний",
    "high": "🔴 Высокий",
}




def _human_working_days(raw: str) -> str:
    names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    days = []
    for part in (raw or '').split(','):
        part = part.strip()
        if part.isdigit():
            idx = int(part)
            if 0 <= idx < 7:
                days.append(names[idx])
    return ', '.join(days) if days else 'все дни'


def _human_quiet(user) -> str:
    if not getattr(user, 'quiet_hours_start', None) or not getattr(user, 'quiet_hours_end', None):
        return 'выключены'
    return f"{user.quiet_hours_start}–{user.quiet_hours_end}"
def kind_human(reminder) -> str:
    if reminder.kind == "once":
        return "Один раз"
    if reminder.kind == "daily":
        return "Каждый день"
    if reminder.kind == "weekly":
        return f"Каждую {WEEKDAY_HUMAN_RU.get(reminder.weekday, reminder.weekday)}"
    return f"Каждые {reminder.interval_hours} ч"


async def ensure_registered_recipients(app: AppContext, recipients: list[int]) -> list[int]:
    missing: list[int] = []
    for uid in recipients:
        if not await app.users_repo.user_exists(uid):
            missing.append(uid)
    return missing


async def _show_main_menu(message: Message, text: str | None = None) -> None:
    await message.answer(text or "Готово.", reply_markup=main_menu_kb())


async def _send_recipient_picker(target_message: Message, state: FSMContext, app: AppContext, hint: str | None = None) -> None:
    users = await app.users_repo.list_users()
    data = await state.get_data()
    selected = data.get("selected_recipients", [])
    page = int(data.get("recipient_page", 0) or 0)
    await target_message.answer(
        hint or "Шаг 5. Выбери получателей кнопками. Себя я отметил по умолчанию.",
        reply_markup=recipient_picker_kb(users, selected, page=page),
    )


async def _create_and_schedule_reminder(
    message: Message,
    state: FSMContext,
    app: AppContext,
    creator,
    *,
    time_part: str | None = None,
    local_dt=None,
) -> None:
    data = await state.get_data()
    kind = data["kind"]
    recipients = data["recipients"]
    text = data["text"]
    category = data.get("category", "work")
    priority = data.get("priority", "medium")
    pre_remind_minutes = int(data.get("pre_remind_minutes", 0) or 0)

    if kind == "once":
        if local_dt is None:
            local_dt = parse_datetime_local(data["date_part"], time_part or data["time_part"], creator.timezone_name)
        if local_dt <= current_time_in_timezone(creator.timezone_name):
            await message.answer("Нельзя создать одноразовое напоминание в прошлое.")
            return
        scheduled_at_utc = local_dt.astimezone(timezone.utc).isoformat()
        reminder_id = await app.reminders_repo.add_once_reminder(
            creator_id=creator.user_id,
            text=text,
            scheduled_at_utc=scheduled_at_utc,
            creator_timezone_at_creation=creator.timezone_name,
            recipients=recipients,
            category=category,
            priority=priority,
            pre_remind_minutes=pre_remind_minutes,
        )
        reminder = await app.reminders_repo.get_reminder(reminder_id)
        if reminder:
            app.scheduler_service.schedule_once_job(reminder, app.bot)
            app.scheduler_service.schedule_pre_jobs(reminder, app.bot)
    elif kind == "daily":
        time_value = time_part or data["time_part"]
        if pre_remind_minutes >= 1440:
            pre_remind_minutes = 0
        reminder_id = await app.reminders_repo.add_daily_reminder(
            creator_id=creator.user_id,
            text=text,
            local_time=time_value,
            creator_timezone_at_creation=creator.timezone_name,
            recipients=recipients,
            category=category,
            priority=priority,
            pre_remind_minutes=pre_remind_minutes,
        )
        reminder = await app.reminders_repo.get_reminder(reminder_id)
        if reminder:
            for uid in recipients:
                user = await app.users_repo.get_user(uid)
                if user:
                    app.scheduler_service.schedule_recurring_job_for_user(reminder, uid, user.timezone_name, app.bot)
                    app.scheduler_service.schedule_pre_jobs(reminder, app.bot, uid, user.timezone_name)
    elif kind == "weekly":
        time_value = time_part or data["time_part"]
        if pre_remind_minutes >= 1440:
            pre_remind_minutes = 0
        reminder_id = await app.reminders_repo.add_weekly_reminder(
            creator_id=creator.user_id,
            text=text,
            weekday=data["weekday"],
            local_time=time_value,
            creator_timezone_at_creation=creator.timezone_name,
            recipients=recipients,
            category=category,
            priority=priority,
            pre_remind_minutes=pre_remind_minutes,
        )
        reminder = await app.reminders_repo.get_reminder(reminder_id)
        if reminder:
            for uid in recipients:
                user = await app.users_repo.get_user(uid)
                if user:
                    app.scheduler_service.schedule_recurring_job_for_user(reminder, uid, user.timezone_name, app.bot)
                    app.scheduler_service.schedule_pre_jobs(reminder, app.bot, uid, user.timezone_name)
    else:
        if local_dt is None:
            local_dt = parse_datetime_local(data["date_part"], time_part or data["time_part"], creator.timezone_name)
        if local_dt <= current_time_in_timezone(creator.timezone_name):
            await message.answer("Нельзя создать интервал в прошлом.")
            return
        reminder_id = await app.reminders_repo.add_interval_reminder(
            creator_id=creator.user_id,
            text=text,
            interval_hours=int(data["interval_hours"]),
            start_at_utc=local_dt.astimezone(timezone.utc).isoformat(),
            creator_timezone_at_creation=creator.timezone_name,
            recipients=recipients,
            category=category,
            priority=priority,
            pre_remind_minutes=pre_remind_minutes if pre_remind_minutes < int(data["interval_hours"]) * 60 else 0,
        )
        reminder = await app.reminders_repo.get_reminder(reminder_id)
        if reminder:
            app.scheduler_service.schedule_interval_job(reminder, app.bot)
            app.scheduler_service.schedule_pre_jobs(reminder, app.bot)

    await app.history_service.log(
        reminder_id,
        creator.user_id,
        "created",
        {"kind": kind, "category": category, "priority": priority, "pre": pre_remind_minutes},
    )
    await state.clear()
    await message.answer(
        "Напоминание создано.\n\n"
        f"ID: {reminder_id}\n"
        f"Категория: {CATEGORY_LABELS.get(category, category)}\n"
        f"Приоритет: {PRIORITY_LABELS.get(priority, priority)}\n"
        f"Предупреждение заранее: {'нет' if pre_remind_minutes == 0 else str(pre_remind_minutes) + ' мин'}\n"
        f"Получателей: {len(recipients)}\n"
        f"Текст: {text}",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_main_menu(message, "Главное меню")


@router.message(F.text == MAIN_MENU_TEXTS["create"])
async def create_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Какое напоминание нужно создать?", reply_markup=cancel_kb())
    await message.answer("Выбери тип напоминания:", reply_markup=reminder_type_kb())


@router.callback_query(F.data.startswith("create_kind:"))
async def choose_kind(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(kind=kind)
    await state.set_state(ReminderFlow.waiting_for_text)
    await callback.message.answer("Шаг 1. Напиши текст напоминания.", reply_markup=cancel_kb())
    await callback.answer()


@router.message(F.text == MAIN_MENU_TEXTS["cancel"])
@router.message(Command("cancel"))
async def cancel_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_main_menu(message, "Действие отменено.")


@router.message(ReminderFlow.waiting_for_text)
async def flow_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым.")
        return
    await state.update_data(text=text)
    await state.set_state(ReminderFlow.waiting_for_category)
    await message.answer("Шаг 2. Выбери категорию.", reply_markup=categories_kb())


@router.callback_query(ReminderFlow.waiting_for_category, F.data.startswith("category:"))
async def flow_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(ReminderFlow.waiting_for_priority)
    await callback.message.answer("Шаг 3. Выбери приоритет.", reply_markup=priorities_kb())
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_priority, F.data.startswith("priority:"))
async def flow_priority(callback: CallbackQuery, state: FSMContext) -> None:
    priority = callback.data.split(":", 1)[1]
    await state.update_data(priority=priority)
    data = await state.get_data()
    await state.set_state(ReminderFlow.waiting_for_pre_remind)
    await callback.message.answer("Шаг 4. Нужно ли предупредить заранее?", reply_markup=pre_remind_kb(data["kind"]))
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_pre_remind, F.data.startswith("pre:"))
async def flow_pre(callback: CallbackQuery, state: FSMContext, app: AppContext) -> None:
    minutes = int(callback.data.split(":", 1)[1])
    creator = await app.users_repo.get_user(callback.from_user.id)
    default_selected = [creator.user_id] if creator else []
    await state.update_data(pre_remind_minutes=minutes, selected_recipients=default_selected, recipient_page=0)
    await state.set_state(ReminderFlow.waiting_for_recipients)
    await _send_recipient_picker(callback.message, state, app)
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data.startswith("recipient_toggle:"))
async def recipients_toggle(callback: CallbackQuery, state: FSMContext, app: AppContext) -> None:
    _, user_id_raw, page_raw = callback.data.split(":")
    user_id = int(user_id_raw)
    page = int(page_raw)
    data = await state.get_data()
    selected = set(data.get("selected_recipients", []))
    if user_id in selected:
        selected.remove(user_id)
    else:
        selected.add(user_id)
    await state.update_data(selected_recipients=list(selected), recipient_page=page)
    users = await app.users_repo.list_users()
    await callback.message.edit_reply_markup(reply_markup=recipient_picker_kb(users, list(selected), page=page))
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data.startswith("recipient_page:"))
async def recipients_page(callback: CallbackQuery, state: FSMContext, app: AppContext) -> None:
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected = data.get("selected_recipients", [])
    await state.update_data(recipient_page=page)
    users = await app.users_repo.list_users()
    await callback.message.edit_reply_markup(reply_markup=recipient_picker_kb(users, selected, page=page))
    await callback.answer()


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data == "recipient_manual")
async def recipients_manual(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReminderFlow.waiting_for_recipients_manual)
    await callback.message.answer(
        "Введи дополнительные user_id через запятую. Пример: 123,456. Напиши 0, если не нужно.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(ReminderFlow.waiting_for_recipients_manual)
async def recipients_manual_text(message: Message, state: FSMContext, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    raw = (message.text or "").strip()
    data = await state.get_data()
    selected = set(data.get("selected_recipients", []))
    if raw != "0":
        try:
            extra = normalize_recipients(raw)
        except ValueError:
            await message.answer("Список должен быть в формате: 123,456,789")
            return
        selected.update(extra)
    selected.add(creator.user_id)
    missing = await ensure_registered_recipients(app, list(selected))
    if missing:
        await message.answer(
            "Эти пользователи еще не запускали бота и не смогут получать уведомления:\n" + "\n".join(map(str, missing))
        )
        return
    await state.update_data(selected_recipients=list(selected))
    await state.set_state(ReminderFlow.waiting_for_recipients)
    await _send_recipient_picker(message, state, app, "Готово. Можно продолжать выбор или нажать «Готово».")


@router.callback_query(ReminderFlow.waiting_for_recipients, F.data == "recipient_done")
async def recipients_done(callback: CallbackQuery, state: FSMContext, app: AppContext) -> None:
    creator = await app.users_repo.get_user(callback.from_user.id)
    if not creator:
        await callback.answer("Сначала /start", show_alert=True)
        return
    data = await state.get_data()
    recipients = list(dict.fromkeys(data.get("selected_recipients", [])))
    if creator.user_id not in recipients:
        recipients.append(creator.user_id)
    if not recipients:
        await callback.answer("Нужно выбрать хотя бы одного получателя", show_alert=True)
        return
    missing = await ensure_registered_recipients(app, recipients)
    if missing:
        await callback.answer("Есть незарегистрированные получатели", show_alert=True)
        return
    await state.update_data(recipients=recipients)
    kind = data["kind"]
    if kind == "once":
        await state.set_state(ReminderFlow.waiting_for_when)
        await callback.message.answer(
            "Шаг 6. Введи время. Примеры:\n"
            "• 2026-03-30 14:45\n"
            "• завтра в 9\n"
            "• через 2 часа\n"
            "• в пятницу в 18:00",
            reply_markup=cancel_kb(),
        )
    elif kind == "weekly":
        await state.set_state(ReminderFlow.waiting_for_weekday)
        await callback.message.answer("Шаг 6. Введи день недели: пн, вт, ср, чт, пт, сб, вс", reply_markup=cancel_kb())
    elif kind == "interval":
        await state.set_state(ReminderFlow.waiting_for_interval_hours)
        await callback.message.answer("Шаг 6. Введи интервал в часах. Пример: 4", reply_markup=cancel_kb())
    else:
        await state.set_state(ReminderFlow.waiting_for_time)
        await callback.message.answer("Шаг 6. Введи время. Поддерживается 9, 09:30, в 9:30", reply_markup=cancel_kb())
    await callback.answer()


@router.message(ReminderFlow.waiting_for_interval_hours)
async def flow_interval_hours(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0 or int(raw) > 168:
        await message.answer("Интервал должен быть целым числом часов от 1 до 168.")
        return
    await state.update_data(interval_hours=int(raw))
    await state.set_state(ReminderFlow.waiting_for_when)
    await message.answer(
        "Шаг 7. Введи стартовое время. Примеры: 2026-03-30 14:45, завтра в 9, через 2 часа",
        reply_markup=cancel_kb(),
    )


@router.message(ReminderFlow.waiting_for_when)
async def flow_when(message: Message, state: FSMContext, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    raw = (message.text or "").strip()
    try:
        local_dt = parse_smart_datetime(raw, creator.timezone_name)
    except ValueError:
        await message.answer(
            "Не понял время. Примеры: 2026-03-30 14:45, завтра в 9, через 2 часа, в пятницу в 18:00"
        )
        return
    await state.update_data(date_part=local_dt.strftime("%Y-%m-%d"), time_part=local_dt.strftime("%H:%M"))
    await _create_and_schedule_reminder(message, state, app, creator, local_dt=local_dt)


@router.message(ReminderFlow.waiting_for_date)
async def flow_date(message: Message, state: FSMContext) -> None:
    date_part = (message.text or "").strip()
    try:
        datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        await message.answer("Дата должна быть в формате YYYY-MM-DD")
        return
    await state.update_data(date_part=date_part)
    await state.set_state(ReminderFlow.waiting_for_time)
    await message.answer("Введи время. Поддерживается 9, 09:30, в 9:30")


@router.message(ReminderFlow.waiting_for_weekday)
async def flow_weekday(message: Message, state: FSMContext) -> None:
    try:
        weekday = parse_weekday((message.text or "").strip())
    except ValueError:
        await message.answer("Неверный день недели. Используй пн/вт/ср/чт/пт/сб/вс")
        return
    await state.update_data(weekday=weekday)
    await state.set_state(ReminderFlow.waiting_for_time)
    await message.answer("Шаг 7. Введи время. Поддерживается 9, 09:30, в 9:30")


@router.message(ReminderFlow.waiting_for_time)
async def flow_time(message: Message, state: FSMContext, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    raw_time = (message.text or "").strip()
    try:
        time_part = parse_flexible_time(raw_time)
    except ValueError:
        await message.answer("Время должно быть в формате HH:MM, H или 'в 9:30'")
        return
    await state.update_data(time_part=time_part)
    await _create_and_schedule_reminder(message, state, app, creator, time_part=time_part)


@router.message(F.text == MAIN_MENU_TEXTS["list"])
@router.message(Command("list"))
async def show_my_reminders(message: Message, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    reminders = await app.reminders_repo.list_creator_reminders(creator.user_id)
    if not reminders:
        await message.answer("У тебя пока нет активных напоминаний.", reply_markup=main_menu_kb())
        return
    await message.answer("Твои активные напоминания:", reply_markup=main_menu_kb())
    for reminder in reminders:
        recipients = await app.reminders_repo.get_recipients(reminder.id)
        recipient_labels = []
        for uid in recipients:
            user = await app.users_repo.get_user(uid)
            label = f"@{user.username}" if user and user.username else (user.full_name if user else str(uid))
            recipient_labels.append(label)
        if reminder.kind == "once" and reminder.scheduled_at_utc:
            desc = f"Один раз: {fmt_local_time_for_user(datetime.fromisoformat(reminder.scheduled_at_utc), creator.timezone_name)}"
        elif reminder.kind == "daily":
            desc = f"Каждый день в {reminder.local_time}"
        elif reminder.kind == "weekly":
            desc = f"Каждую {WEEKDAY_HUMAN_RU.get(reminder.weekday, reminder.weekday)} в {reminder.local_time}"
        else:
            start_local = fmt_local_time_for_user(datetime.fromisoformat(reminder.scheduled_at_utc), creator.timezone_name)
            desc = f"Каждые {reminder.interval_hours} ч, старт: {start_local}"

        pre_text = "нет" if not reminder.pre_remind_minutes else f"за {reminder.pre_remind_minutes} мин"
        states = await app.reminders_repo.list_recipient_states(reminder.id)
        state_lines = []
        for state in states:
            user = await app.users_repo.get_user(state.user_id)
            label = f"@{user.username}" if user and user.username else (user.full_name if user else str(state.user_id))
            extra = f", прочитано" if state.acknowledged_at else ""
            if state.last_skipped_reason:
                extra += f", skip={state.last_skipped_reason}"
            state_lines.append(f"- {label}: {state.status}, доставок {state.delivered_count}{extra}")
        states_text = "\n".join(state_lines) if state_lines else "—"
        await message.answer(
            f"<b>ID {reminder.id}</b>\n"
            f"{desc}\n"
            f"Категория: {CATEGORY_LABELS.get(reminder.category, reminder.category)}\n"
            f"Приоритет: {PRIORITY_LABELS.get(reminder.priority, reminder.priority)}\n"
            f"Предупреждение: {pre_text}\n"
            f"Статус: {reminder.status}\n"
            f"Получатели: {', '.join(recipient_labels)}\n"
            f"Состояния по получателям:\n{states_text}\n"
            f"Текст: {reminder.text}",
            reply_markup=reminder_actions_kb(reminder.id),
        )


@router.callback_query(F.data.startswith("reminder_ack:"))
async def reminder_ack(callback: CallbackQuery, app: AppContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Не найдено", show_alert=True)
        return
    recipients = await app.reminders_repo.get_recipients(reminder_id)
    if callback.from_user.id not in recipients and reminder.creator_id != callback.from_user.id:
        await callback.answer("У тебя нет доступа к этому напоминанию", show_alert=True)
        return
    await app.reminders_repo.mark_recipient_ack(reminder_id, callback.from_user.id)
    await app.history_service.log(reminder_id, callback.from_user.id, "acknowledged")
    await callback.answer("Подтверждено")
    await callback.message.answer(f"Получение напоминания {reminder_id} подтверждено.")


@router.callback_query(F.data.startswith("reminder_done:"))
async def reminder_done(callback: CallbackQuery, app: AppContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Не найдено", show_alert=True)
        return
    if reminder.creator_id != callback.from_user.id:
        await callback.answer("Это не твое напоминание", show_alert=True)
        return
    await app.reminders_repo.mark_done(reminder_id)
    await app.history_service.log(reminder_id, callback.from_user.id, "done")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"Напоминание {reminder_id} отмечено как выполненное.")
    await callback.answer("Готово")


@router.callback_query(F.data.startswith("reminder_snooze_menu:"))
async def reminder_snooze_menu(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer("На сколько отложить напоминание?", reply_markup=snooze_kb(reminder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("reminder_snooze:"))
async def reminder_snooze(callback: CallbackQuery, app: AppContext) -> None:
    _, reminder_id_raw, mode = callback.data.split(":", 2)
    reminder_id = int(reminder_id_raw)
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Не найдено", show_alert=True)
        return
    if reminder.creator_id != callback.from_user.id:
        await callback.answer("Это не твое напоминание", show_alert=True)
        return
    run_at = await app.scheduler_service.snooze_reminder(reminder_id, mode, app.bot)
    await app.history_service.log(reminder_id, callback.from_user.id, "snoozed", {"mode": mode})
    await callback.message.answer(f"Отложил напоминание до {run_at.strftime('%d.%m.%Y %H:%M UTC')}.")
    await callback.answer("Отложено")


@router.callback_query(F.data.startswith("reminder_delete:"))
async def delete_reminder_cb(callback: CallbackQuery, app: AppContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Не найдено", show_alert=True)
        return
    ok = await app.reminders_repo.delete_reminder_for_creator(reminder_id, callback.from_user.id)
    if not ok:
        await callback.answer("Это не твое напоминание", show_alert=True)
        return
    app.scheduler_service.remove_all_jobs_for_reminder(reminder, app.scheduler_service.scheduler)
    await app.history_service.log(reminder_id, callback.from_user.id, "deleted")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"Напоминание {reminder_id} удалено.")
    await callback.answer("Удалено")


@router.callback_query(F.data.startswith("reminder_sharecopy:"))
async def share_copy_cb(callback: CallbackQuery, app: AppContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    try:
        link = await app.sharing_service.create_share_link(callback.from_user.id, reminder_id, "copy")
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await app.history_service.log(reminder_id, callback.from_user.id, "share_created", {"mode": "copy"})
    await callback.message.answer(f"Ссылка для копии:\n{link}")
    await callback.answer("Ссылка готова")


@router.callback_query(F.data.startswith("reminder_sharerecipient:"))
async def share_recipient_cb(callback: CallbackQuery, app: AppContext) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    try:
        link = await app.sharing_service.create_share_link(callback.from_user.id, reminder_id, "recipient")
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await app.history_service.log(reminder_id, callback.from_user.id, "share_created", {"mode": "recipient"})
    await callback.message.answer(f"Ссылка для подписки:\n{link}")
    await callback.answer("Ссылка готова")


@router.message(F.text == MAIN_MENU_TEXTS["share"])
@router.message(Command("myshares"))
async def show_shares(message: Message, app: AppContext) -> None:
    shares = await app.shares_repo.list_user_shares(message.from_user.id)
    if not shares:
        await message.answer("У тебя пока нет активных share-ссылок.", reply_markup=main_menu_kb())
        return
    lines = []
    for share in shares:
        link = f"https://t.me/{app.config.bot_username}?start=share_{share.token}" if app.config.bot_username else f"share_{share.token}"
        mode = "копия" if share.share_mode == "copy" else "подписка"
        lines.append(f"Reminder ID: {share.reminder_id}\nРежим: {mode}\nТокен: {share.token}\n{link}")
    await message.answer("\n\n".join(lines), reply_markup=main_menu_kb())


@router.message(F.text == MAIN_MENU_TEXTS["history"])
async def show_history(message: Message, app: AppContext) -> None:
    text = await app.history_service.render_user_history(message.from_user.id)
    await message.answer(text, reply_markup=main_menu_kb())


@router.message(F.text == MAIN_MENU_TEXTS["stats"])
async def show_stats(message: Message, app: AppContext) -> None:
    stats = await app.reminders_repo.get_user_statistics(message.from_user.id)
    events = await app.events_repo.count_events_by_type_for_user(message.from_user.id)
    cat_lines = "\n".join(f"- {CATEGORY_LABELS.get(k, k)}: {v}" for k, v in stats["categories"].items()) or "—"
    pr_lines = "\n".join(f"- {PRIORITY_LABELS.get(k, k)}: {v}" for k, v in stats["priorities"].items()) or "—"
    await message.answer(
        "📊 Статистика\n\n"
        f"Всего создано: {stats['total']}\n"
        f"Активных: {stats.get('active', 0)}\n"
        f"Выполнено: {stats.get('done', 0)}\n"
        f"Пропущено: {stats.get('missed', 0)}\n"
        f"Отложено сейчас: {stats.get('snoozed', 0)}\n"
        f"С предуведомлением: {stats.get('with_pre_remind', 0)}\n"
        f"Интервальных: {stats.get('interval', 0)}\n\n"
        "По категориям:\n"
        f"{cat_lines}\n\n"
        "По приоритетам:\n"
        f"{pr_lines}\n\n"
        f"Отправлено уведомлений: {events.get('sent', 0)}\n"
        f"Отправлено заранее: {events.get('pre_sent', 0)}\n"
        f"Отложено: {events.get('snoozed', 0)}\n"
        f"Подтверждено прочтение: {events.get('acknowledged', 0)}\n"
        f"Пропущено по quiet hours / рабочим дням: {events.get('skipped', 0)}\n",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == MAIN_MENU_TEXTS["settings"])
async def show_settings(message: Message, app: AppContext) -> None:
    user = await app.users_repo.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота: /start")
        return
    await message.answer(
        f"Текущая таймзона: {user.timezone_name}\n"
        f"Тихие часы: {_human_quiet(user)}\n"
        f"Рабочие дни: {_human_working_days(user.working_days)}\n"
        f"Выбери действие:",
        reply_markup=settings_kb(),
    )


@router.callback_query(F.data == "settings:time")
async def settings_time(callback: CallbackQuery, app: AppContext) -> None:
    user = await app.users_repo.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start", show_alert=True)
        return
    now_local = current_time_in_timezone(user.timezone_name)
    await callback.message.answer(f"Твоя таймзона: {user.timezone_name}\nЛокальное время: {now_local.strftime('%d.%m.%Y %H:%M:%S')}")
    await callback.answer()


@router.callback_query(F.data == "settings:timezone")
async def settings_timezone(callback: CallbackQuery, app: AppContext) -> None:
    user = await app.users_repo.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start", show_alert=True)
        return
    await callback.message.answer(f"Текущая таймзона: {user.timezone_name}")
    await callback.answer()


@router.callback_query(F.data.startswith("settings:settz:"))
async def settings_settz(callback: CallbackQuery, app: AppContext) -> None:
    tz_name = callback.data.split(":", 2)[2]
    try:
        validate_timezone_name(tz_name)
    except ValueError:
        await callback.answer("Неверная таймзона", show_alert=True)
        return
    ok = await app.users_repo.set_user_timezone(callback.from_user.id, tz_name)
    if not ok:
        await callback.answer("Не удалось обновить", show_alert=True)
        return
    await app.scheduler_service.reschedule_user_recurring_jobs(callback.from_user.id, app.bot)
    now_local = current_time_in_timezone(tz_name)
    await callback.message.answer(f"Таймзона обновлена: {tz_name}\nНовое локальное время: {now_local.strftime('%d.%m.%Y %H:%M:%S')}")
    await callback.answer("Обновлено")


@router.message(F.text == MAIN_MENU_TEXTS["myid"])
@router.message(Command("myid"))
async def show_myid(message: Message) -> None:
    await message.answer(f"Твой Telegram user_id: <code>{message.from_user.id}</code>", reply_markup=main_menu_kb())


@router.callback_query(F.data == "settings:quiet:off")
async def settings_quiet_off(callback: CallbackQuery, app: AppContext) -> None:
    await app.users_repo.set_quiet_hours(callback.from_user.id, None, None)
    await callback.message.answer("Тихие часы отключены.")
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:quiet:23-08")
async def settings_quiet_2308(callback: CallbackQuery, app: AppContext) -> None:
    await app.users_repo.set_quiet_hours(callback.from_user.id, "23:00", "08:00")
    await callback.message.answer("Тихие часы включены: 23:00–08:00")
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:wd:weekdays")
async def settings_workdays_weekdays(callback: CallbackQuery, app: AppContext) -> None:
    await app.users_repo.set_working_days(callback.from_user.id, "0,1,2,3,4")
    await callback.message.answer("Рабочие дни обновлены: пн, вт, ср, чт, пт")
    await callback.answer("Сохранено")


@router.callback_query(F.data == "settings:wd:all")
async def settings_workdays_all(callback: CallbackQuery, app: AppContext) -> None:
    await app.users_repo.set_working_days(callback.from_user.id, "0,1,2,3,4,5,6")
    await callback.message.answer("Рабочие дни обновлены: все дни")
    await callback.answer("Сохранено")
