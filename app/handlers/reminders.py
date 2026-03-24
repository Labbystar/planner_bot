from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards.menu import main_menu_kb

router = Router()


@router.message(Command("addmulti"))
@router.message(Command("adddaily"))
@router.message(Command("addweekly"))
async def command_hint(message: Message) -> None:
    await message.answer(
        "Теперь напоминания удобнее создавать через кнопку «➕ Создать напоминание».\n"
        "Там доступны одноразовые, ежедневные, еженедельные и интервальные сценарии, плюс предуведомления.",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("delete"))
async def delete_hint(message: Message) -> None:
    await message.answer(
        "Чтобы удалить напоминание, открой «📋 Мои напоминания» и нажми кнопку «🗑 Удалить» под нужной карточкой.",
        reply_markup=main_menu_kb(),
    )
