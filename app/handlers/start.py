from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app.context import AppContext
from app.keyboards.menu import main_menu_kb
from app.keyboards.share import share_accept_kb

router = Router()


@router.message(CommandStart(deep_link=False))
async def cmd_start(message: Message, app: AppContext) -> None:
    await app.users_repo.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        timezone_name=app.config.default_timezone,
    )
    user = await app.users_repo.get_user(message.from_user.id)

    await message.answer(
        "Привет. Я planner-бот.\n\n"
        f"Твоя текущая таймзона: {user.timezone_name if user else app.config.default_timezone}\n\n"
        "Пользуйся кнопками снизу. Через них можно создать напоминание, посмотреть свои задачи, открыть настройки и share-ссылки.",
        reply_markup=main_menu_kb(),
    )


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_payload(message: Message, command: CommandObject, app: AppContext) -> None:
    await app.users_repo.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        timezone_name=app.config.default_timezone,
    )

    payload = command.args or ""
    if payload.startswith("share_"):
        token = payload.removeprefix("share_")
        try:
            _, preview = await app.sharing_service.get_share_preview(token)
        except ValueError as exc:
            await message.answer(str(exc), reply_markup=main_menu_kb())
            return

        await message.answer(preview, reply_markup=share_accept_kb(token))
        return

    await message.answer("Бот запущен.", reply_markup=main_menu_kb())
