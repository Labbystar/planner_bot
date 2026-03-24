from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.context import AppContext
from app.keyboards.menu import (
    MAIN_MENU_TEXTS,
    cancel_kb,
    main_menu_kb,
    reminder_actions_kb,
    reminder_type_kb,
    settings_kb,
)
from app.states.reminder_flow import ReminderFlow
from app.utils.parsing import normalize_recipients
from app.utils.timezones import (
    WEEKDAY_HUMAN_RU,
    current_time_in_timezone,
    fmt_local_time_for_user,
    parse_datetime_local,
    parse_hhmm,
    parse_weekday,
    validate_timezone_name,
)

router = Router()


async def ensure_registered_recipients(app: AppContext, recipients: list[int]) -> list[int]:
    missing: list[int] = []
    for uid in recipients:
        if not await app.users_repo.user_exists(uid):
            missing.append(uid)
    return missing


async def _show_main_menu(message: Message, text: str | None = None) -> None:
    await message.answer(text or "Готово.", reply_markup=main_menu_kb())


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
    await callback.message.answer("Шаг 1 из 4. Напиши текст напоминания.", reply_markup=cancel_kb())
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
    await state.set_state(ReminderFlow.waiting_for_recipients)
    await message.answer(
        "Шаг 2. Введи получателей через запятую.\n"
        "Пример: 123456789,987654321\n"
        "Можно указать только свой ID, а посмотреть его кнопкой «🆔 Мой ID»."
    )


@router.message(ReminderFlow.waiting_for_recipients)
async def flow_recipients(message: Message, state: FSMContext, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return

    raw = (message.text or "").strip()
    try:
        recipients = normalize_recipients(raw)
    except ValueError:
        await message.answer("Список должен быть в формате: 123,456,789")
        return

    if not recipients:
        await message.answer("Список получателей пуст.")
        return

    if creator.user_id not in recipients:
        recipients.append(creator.user_id)

    missing = await ensure_registered_recipients(app, recipients)
    if missing:
        await message.answer(
            "Эти пользователи еще не запускали бота и не смогут получать уведомления:\n"
            + "\n".join(map(str, missing))
        )
        return

    await state.update_data(recipients=recipients)
    data = await state.get_data()
    kind = data["kind"]

    if kind == "once":
        await state.set_state(ReminderFlow.waiting_for_date)
        await message.answer("Шаг 3. Введи дату в формате YYYY-MM-DD. Пример: 2026-03-30")
    elif kind == "weekly":
        await state.set_state(ReminderFlow.waiting_for_weekday)
        await message.answer("Шаг 3. Введи день недели: пн, вт, ср, чт, пт, сб, вс")
    else:
        await state.set_state(ReminderFlow.waiting_for_time)
        await message.answer("Шаг 3. Введи время в формате HH:MM. Пример: 09:30")


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
    await message.answer("Шаг 4. Введи время в формате HH:MM. Пример: 14:45")


@router.message(ReminderFlow.waiting_for_weekday)
async def flow_weekday(message: Message, state: FSMContext) -> None:
    try:
        weekday = parse_weekday((message.text or "").strip())
    except ValueError:
        await message.answer("Неверный день недели. Используй пн/вт/ср/чт/пт/сб/вс")
        return

    await state.update_data(weekday=weekday)
    await state.set_state(ReminderFlow.waiting_for_time)
    await message.answer("Шаг 4. Введи время в формате HH:MM. Пример: 10:00")


@router.message(ReminderFlow.waiting_for_time)
async def flow_time(message: Message, state: FSMContext, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return

    time_part = (message.text or "").strip()
    try:
        parse_hhmm(time_part)
    except ValueError:
        await message.answer("Время должно быть в формате HH:MM")
        return

    data = await state.get_data()
    kind = data["kind"]
    recipients: list[int] = data["recipients"]
    text: str = data["text"]

    if kind == "once":
        local_dt = parse_datetime_local(data["date_part"], time_part, creator.timezone_name)
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
        )
        reminder = await app.reminders_repo.get_reminder(reminder_id)
        if reminder:
            app.scheduler_service.schedule_once_job(reminder, app.bot)

        await state.clear()
        await message.answer(
            "Напоминание создано.\n\n"
            f"ID: {reminder_id}\n"
            f"Тип: одноразовое\n"
            f"Когда: {local_dt.strftime('%d.%m.%Y %H:%M')} ({creator.timezone_name})\n"
            f"Получателей: {len(recipients)}\n"
            f"Текст: {text}",
            reply_markup=main_menu_kb(),
        )
        return

    if kind == "daily":
        reminder_id = await app.reminders_repo.add_daily_reminder(
            creator_id=creator.user_id,
            text=text,
            local_time=time_part,
            creator_timezone_at_creation=creator.timezone_name,
            recipients=recipients,
        )
        reminder = await app.reminders_repo.get_reminder(reminder_id)
        if reminder:
            for uid in recipients:
                user = await app.users_repo.get_user(uid)
                if user:
                    app.scheduler_service.schedule_recurring_job_for_user(reminder, uid, user.timezone_name, app.bot)

        await state.clear()
        await message.answer(
            "Напоминание создано.\n\n"
            f"ID: {reminder_id}\n"
            f"Тип: ежедневное\n"
            f"Время: {time_part}\n"
            f"Получателей: {len(recipients)}\n"
            f"Текст: {text}",
            reply_markup=main_menu_kb(),
        )
        return

    reminder_id = await app.reminders_repo.add_weekly_reminder(
        creator_id=creator.user_id,
        text=text,
        weekday=data["weekday"],
        local_time=time_part,
        creator_timezone_at_creation=creator.timezone_name,
        recipients=recipients,
    )
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if reminder:
        for uid in recipients:
            user = await app.users_repo.get_user(uid)
            if user:
                app.scheduler_service.schedule_recurring_job_for_user(reminder, uid, user.timezone_name, app.bot)

    await state.clear()
    await message.answer(
        "Напоминание создано.\n\n"
        f"ID: {reminder_id}\n"
        f"Тип: еженедельное\n"
        f"День: {WEEKDAY_HUMAN_RU[data['weekday']]}\n"
        f"Время: {time_part}\n"
        f"Получателей: {len(recipients)}\n"
        f"Текст: {text}",
        reply_markup=main_menu_kb(),
    )


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
        if reminder.kind == "once" and reminder.scheduled_at_utc:
            desc = f"Один раз: {fmt_local_time_for_user(datetime.fromisoformat(reminder.scheduled_at_utc), creator.timezone_name)}"
        elif reminder.kind == "daily":
            desc = f"Каждый день в {reminder.local_time}"
        else:
            desc = f"Каждую {WEEKDAY_HUMAN_RU.get(reminder.weekday, reminder.weekday)} в {reminder.local_time}"

        await message.answer(
            f"<b>ID {reminder.id}</b>\n"
            f"{desc}\n"
            f"Получатели: {', '.join(map(str, recipients))}\n"
            f"Текст: {reminder.text}",
            reply_markup=reminder_actions_kb(reminder.id),
        )


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

    if reminder.kind == "once":
        job = app.scheduler_service.scheduler.get_job(app.scheduler_service.once_job_id(reminder_id))
        if job:
            app.scheduler_service.scheduler.remove_job(app.scheduler_service.once_job_id(reminder_id))
    else:
        recipients = await app.reminders_repo.get_recipients(reminder_id)
        for uid in recipients:
            job_id = app.scheduler_service.recurring_job_id(reminder_id, uid)
            job = app.scheduler_service.scheduler.get_job(job_id)
            if job:
                app.scheduler_service.scheduler.remove_job(job_id)

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


@router.message(F.text == MAIN_MENU_TEXTS["settings"])
async def show_settings(message: Message, app: AppContext) -> None:
    user = await app.users_repo.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота: /start")
        return
    await message.answer(
        f"Текущая таймзона: {user.timezone_name}\nВыбери действие:",
        reply_markup=settings_kb(),
    )


@router.callback_query(F.data == "settings:time")
async def settings_time(callback: CallbackQuery, app: AppContext) -> None:
    user = await app.users_repo.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start", show_alert=True)
        return
    now_local = current_time_in_timezone(user.timezone_name)
    await callback.message.answer(
        f"Твоя таймзона: {user.timezone_name}\nЛокальное время: {now_local.strftime('%d.%m.%Y %H:%M:%S')}"
    )
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
    await callback.message.answer(
        f"Таймзона обновлена: {tz_name}\n"
        f"Новое локальное время: {now_local.strftime('%d.%m.%Y %H:%M:%S')}"
    )
    await callback.answer("Обновлено")


@router.message(F.text == MAIN_MENU_TEXTS["myid"])
@router.message(Command("myid"))
async def show_myid(message: Message) -> None:
    await message.answer(f"Твой Telegram user_id: <code>{message.from_user.id}</code>", reply_markup=main_menu_kb())
