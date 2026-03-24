from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards.menu import main_menu_keyboard
from app.services.users import upsert_user, get_user

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    user = await get_user(message.from_user.id)

    await message.answer(
        f"Привет. Я planner-бот.\n\n"
        f"Твоя таймзона: {user.timezone_name}\n\n"
        f"Используй кнопки ниже 👇",
        reply_markup=main_menu_keyboard()
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
            await message.answer(str(exc))
            return

        await message.answer(preview, reply_markup=share_accept_kb(token))
        return

    await message.answer("Бот запущен.")
