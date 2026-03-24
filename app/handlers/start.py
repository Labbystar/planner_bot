from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards.menu import main_menu
from app.services.users import get_user, upsert_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    user = await get_user(message.from_user.id)
    await message.answer(
        "<b>Привет. Я NapomniMne.</b>\n\n"
        f"🌍 Твоя таймзона: <b>{user['timezone_name']}</b>\n\n"
        "Используй кнопки ниже: быстрое создание, активные задачи, настройки.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )
