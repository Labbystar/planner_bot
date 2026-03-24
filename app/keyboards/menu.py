from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.text == "➕ Создать напоминание")
async def create_reminder_menu(message: Message):
    await message.answer(
        "Выбери тип:\n\n"
        "/addmulti — одноразовое\n"
        "/adddaily — ежедневное\n"
        "/addweekly — еженедельное"
    )


@router.message(F.text == "📋 Мои напоминания")
async def list_menu(message: Message):
    await message.answer("Введи /list")


@router.message(F.text == "🔗 Поделиться")
async def share_menu(message: Message):
    await message.answer(
        "Поделиться напоминанием:\n\n"
        "/sharecopy ID — копия\n"
        "/sharerecipient ID — добавить получателя"
    )


@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    await message.answer(
        "Настройки:\n\n"
        "/timezone — текущая\n"
        "/settz Europe/Moscow — сменить\n"
        "/time — текущее время"
    )