from datetime import timezone

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.context import AppContext
from app.utils.parsing import normalize_recipients
from app.utils.timezones import WEEKDAY_HUMAN_RU, fmt_local_time_for_user, parse_datetime_local, parse_hhmm, parse_weekday, current_time_in_timezone

router = Router()


async def ensure_registered_recipients(app: AppContext, recipients: list[int]) -> list[int]:
    missing: list[int] = []
    for uid in recipients:
        if not await app.users_repo.user_exists(uid):
            missing.append(uid)
    return missing


@router.message(Command("addmulti"))
async def cmd_addmulti(message: Message, command: CommandObject, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    if not command.args:
        await message.answer("Формат: /addmulti 2026-03-25 15:00 111111111,222222222 Созвон")
        return

    parts = command.args.split(" ", 3)
    if len(parts) < 4:
        await message.answer("Неверный формат. Нужно: дата время список_user_id текст")
        return

    date_part, time_part, recipients_raw, text = parts
    try:
        local_dt = parse_datetime_local(date_part, time_part, creator.timezone_name)
    except ValueError:
        await message.answer("Дата и время должны быть в формате YYYY-MM-DD HH:MM")
        return

    now_local = current_time_in_timezone(creator.timezone_name)
    if local_dt <= now_local:
        await message.answer("Нельзя создать одноразовое напоминание в прошлое")
        return

    try:
        recipients = normalize_recipients(recipients_raw)
    except ValueError:
        await message.answer("Список получателей должен быть в виде: 123,456,789")
        return

    if creator.user_id not in recipients:
        recipients.append(creator.user_id)

    missing = await ensure_registered_recipients(app, recipients)
    if missing:
        await message.answer("Эти пользователи еще не запускали бота:\n" + "\n".join(map(str, missing)))
        return

    scheduled_at_utc = local_dt.astimezone(timezone.utc).isoformat()
    reminder_id = await app.reminders_repo.add_once_reminder(
        creator_id=creator.user_id,
        text=text.strip(),
        scheduled_at_utc=scheduled_at_utc,
        creator_timezone_at_creation=creator.timezone_name,
        recipients=recipients,
    )
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if reminder:
        app.scheduler_service.schedule_once_job(reminder, app.bot)

    await message.answer(
        "Одноразовое напоминание создано.\n\n"
        f"ID: {reminder_id}\n"
        f"Локальное время создателя: {local_dt.strftime('%d.%m.%Y %H:%M')} ({creator.timezone_name})\n"
        f"UTC: {scheduled_at_utc}\n"
        f"Получателей: {len(recipients)}\n"
        f"Текст: {text.strip()}"
    )


@router.message(Command("adddaily"))
async def cmd_adddaily(message: Message, command: CommandObject, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    if not command.args:
        await message.answer("Формат: /adddaily 09:30 111111111,222222222 Ежедневный статус")
        return

    parts = command.args.split(" ", 2)
    if len(parts) < 3:
        await message.answer("Неверный формат. Нужно: HH:MM список_user_id текст")
        return

    time_part, recipients_raw, text = parts
    try:
        parse_hhmm(time_part)
    except ValueError:
        await message.answer("Время должно быть в формате HH:MM")
        return

    try:
        recipients = normalize_recipients(recipients_raw)
    except ValueError:
        await message.answer("Список получателей должен быть в виде: 123,456,789")
        return

    if creator.user_id not in recipients:
        recipients.append(creator.user_id)

    missing = await ensure_registered_recipients(app, recipients)
    if missing:
        await message.answer("Эти пользователи еще не запускали бота:\n" + "\n".join(map(str, missing)))
        return

    reminder_id = await app.reminders_repo.add_daily_reminder(
        creator_id=creator.user_id,
        text=text.strip(),
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

    await message.answer(
        "Ежедневное напоминание создано.\n\n"
        f"ID: {reminder_id}\n"
        f"Локальное время: {time_part}\n"
        f"Получателей: {len(recipients)}\n"
        f"Текст: {text.strip()}\n\n"
        "Каждый получатель будет получать его по своей текущей таймзоне."
    )


@router.message(Command("addweekly"))
async def cmd_addweekly(message: Message, command: CommandObject, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    if not command.args:
        await message.answer("Формат: /addweekly пн 09:30 111111111,222222222 Планерка")
        return

    parts = command.args.split(" ", 3)
    if len(parts) < 4:
        await message.answer("Неверный формат. Нужно: weekday HH:MM список_user_id текст")
        return

    weekday_raw, time_part, recipients_raw, text = parts
    try:
        weekday = parse_weekday(weekday_raw)
        parse_hhmm(time_part)
        recipients = normalize_recipients(recipients_raw)
    except ValueError:
        await message.answer("Проверь день недели, время и список получателей")
        return

    if creator.user_id not in recipients:
        recipients.append(creator.user_id)

    missing = await ensure_registered_recipients(app, recipients)
    if missing:
        await message.answer("Эти пользователи еще не запускали бота:\n" + "\n".join(map(str, missing)))
        return

    reminder_id = await app.reminders_repo.add_weekly_reminder(
        creator_id=creator.user_id,
        text=text.strip(),
        weekday=weekday,
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

    await message.answer(
        "Еженедельное напоминание создано.\n\n"
        f"ID: {reminder_id}\n"
        f"День: {WEEKDAY_HUMAN_RU[weekday]}\n"
        f"Локальное время: {time_part}\n"
        f"Получателей: {len(recipients)}\n"
        f"Текст: {text.strip()}"
    )


@router.message(Command("list"))
async def cmd_list(message: Message, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return

    reminders = await app.reminders_repo.list_creator_reminders(creator.user_id)
    if not reminders:
        await message.answer("У тебя нет активных созданных напоминаний")
        return

    lines: list[str] = []
    for reminder in reminders:
        recipients = await app.reminders_repo.get_recipients(reminder.id)
        if reminder.kind == "once" and reminder.scheduled_at_utc:
            from datetime import datetime
            desc = f"одноразовое: {fmt_local_time_for_user(datetime.fromisoformat(reminder.scheduled_at_utc), creator.timezone_name)} ({creator.timezone_name})"
        elif reminder.kind == "daily":
            desc = f"ежедневно в {reminder.local_time}"
        else:
            desc = f"еженедельно: {WEEKDAY_HUMAN_RU.get(reminder.weekday, reminder.weekday)} {reminder.local_time}"
        lines.append(
            f"ID: {reminder.id}\n"
            f"Тип: {desc}\n"
            f"Получатели: {', '.join(map(str, recipients))}\n"
            f"Текст: {reminder.text}"
        )

    await message.answer("\n\n".join(lines))


@router.message(Command("delete"))
async def cmd_delete(message: Message, command: CommandObject, app: AppContext) -> None:
    creator = await app.users_repo.get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала запусти бота: /start")
        return
    if not command.args or not command.args.isdigit():
        await message.answer("Формат: /delete ID")
        return

    reminder_id = int(command.args)
    reminder = await app.reminders_repo.get_reminder(reminder_id)
    if not reminder:
        await message.answer("Напоминание не найдено")
        return

    ok = await app.reminders_repo.delete_reminder_for_creator(reminder_id, creator.user_id)
    if not ok:
        await message.answer("Напоминание не найдено или оно тебе не принадлежит")
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

    await message.answer(f"Напоминание {reminder_id} удалено")
