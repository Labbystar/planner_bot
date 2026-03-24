from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.context import AppContext
from app.utils.timezones import current_time_in_timezone, validate_timezone_name

router = Router()


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Твой Telegram user_id: {message.from_user.id}")


@router.message(Command("timezone"))
async def cmd_timezone(message: Message, app: AppContext) -> None:
    user = await app.users_repo.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота: /start")
        return
    await message.answer(f"Текущая таймзона: {user.timezone_name}")


@router.message(Command("time"))
async def cmd_time(message: Message, app: AppContext) -> None:
    user = await app.users_repo.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота: /start")
        return
    now_local = current_time_in_timezone(user.timezone_name)
    await message.answer(
        f"Твоя таймзона: {user.timezone_name}\n"
        f"Локальное время: {now_local.strftime('%d.%m.%Y %H:%M:%S')}"
    )


@router.message(Command("settz"))
async def cmd_settz(message: Message, command: CommandObject, app: AppContext) -> None:
    user = await app.users_repo.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота: /start")
        return

    if not command.args:
        await message.answer("Формат: /settz Europe/Moscow")
        return

    tz_name = command.args.strip()
    try:
        validate_timezone_name(tz_name)
    except ValueError:
        await message.answer("Не удалось распознать таймзону. Примеры: Asia/Novosibirsk, Europe/Moscow")
        return

    ok = await app.users_repo.set_user_timezone(message.from_user.id, tz_name)
    if not ok:
        await message.answer("Не удалось обновить таймзону")
        return

    await app.scheduler_service.reschedule_user_recurring_jobs(message.from_user.id, app.bot)
    now_local = current_time_in_timezone(tz_name)
    await message.answer(
        f"Таймзона обновлена: {tz_name}\n"
        f"Новое локальное время: {now_local.strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        "Одноразовые напоминания не сдвигаются.\n"
        "Повторяющиеся будут идти по новой таймзоне."
    )
