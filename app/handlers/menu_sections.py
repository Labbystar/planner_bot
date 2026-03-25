from aiogram import Router, F
from aiogram.types import Message

from app.keyboards.menu import main_menu, service_menu, tasks_menu, team_menu

router = Router()


@router.message(F.text == "📋 Задачи")
async def open_tasks_menu(message: Message) -> None:
    await message.answer(
        "📋 Раздел задач\n\n"
        "Здесь собраны списки, календарь, поиск, просроченные и экспорт.",
        reply_markup=tasks_menu(),
    )


@router.message(F.text == "📊 Команда")
async def open_team_menu(message: Message) -> None:
    await message.answer(
        "📊 Раздел команды\n\n"
        "Здесь собраны статистика по сотрудникам и админка.",
        reply_markup=team_menu(),
    )


@router.message(F.text == "⚙️ Сервис")
async def open_service_menu(message: Message) -> None:
    await message.answer(
        "⚙️ Сервисный раздел\n\n"
        "Здесь находятся настройки и служебные функции.",
        reply_markup=service_menu(),
    )


@router.message(F.text == "⬅️ Назад в меню")
async def back_to_main_menu(message: Message) -> None:
    await message.answer("Главное меню", reply_markup=main_menu())
