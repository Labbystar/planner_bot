from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.create import categories_kb, priorities_kb
from app.keyboards.menu import main_menu
from app.services.reminders import create_reminder
from app.services.users import get_user
from app.utils.time import parse_user_time

router = Router()


class CreateReminder(StatesGroup):
    text = State()
    category = State()
    priority = State()
    when = State()
    note = State()


@router.message(F.text == "➕ Создать")
async def start_create(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CreateReminder.text)
    await message.answer("<b>Шаг 1/4</b>\nНапиши короткий текст задачи.", parse_mode="HTML")


@router.message(F.text == "⚡ Быстро")
async def quick_create_hint(message: Message) -> None:
    await message.answer(
        "Отправь одной строкой:\n"
        "<code>Текст | завтра в 9</code>\n\n"
        "Пример:\n<code>Позвонить клиенту | завтра в 9</code>",
        parse_mode="HTML",
    )


@router.message(CreateReminder.text)
async def got_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text.strip())
    await state.set_state(CreateReminder.category)
    await message.answer("<b>Шаг 2/4</b>\nВыбери категорию.", reply_markup=categories_kb(), parse_mode="HTML")


@router.callback_query(CreateReminder.category, F.data.startswith("cat:"))
async def got_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(category=callback.data.split(":", 1)[1])
    await state.set_state(CreateReminder.priority)
    await callback.message.answer("<b>Шаг 3/4</b>\nВыбери приоритет.", reply_markup=priorities_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(CreateReminder.priority, F.data.startswith("prio:"))
async def got_priority(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(priority=callback.data.split(":", 1)[1])
    await state.set_state(CreateReminder.when)
    await callback.message.answer(
        "<b>Шаг 4/4</b>\nКогда прислать уведомление?\n\n"
        "Примеры:\n"
        "• <code>2026-03-30 14:45</code>\n"
        "• <code>завтра в 9</code>\n"
        "• <code>через 2 часа</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(CreateReminder.when)
async def got_when(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start")
        return
    try:
        dt_local = parse_user_time(message.text, user["timezone_name"])
    except ValueError:
        await message.answer("Не понял дату/время. Попробуй так: <code>завтра в 9</code> или <code>2026-03-30 14:45</code>", parse_mode="HTML")
        return

    data = await state.get_data()
    reminder_id = await create_reminder(
        owner_user_id=message.from_user.id,
        text=data["text"],
        scheduled_at_utc=dt_local.astimezone(timezone.utc).isoformat(),
        category=data["category"],
        priority=data["priority"],
        note=None,
    )
    await state.clear()
    await message.answer(
        f"✅ Напоминание создано. ID: {reminder_id}\n📅 {dt_local.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=main_menu(),
    )


@router.message(F.text.contains("|"))
async def quick_create(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return
    left, right = [x.strip() for x in message.text.split("|", 1)]
    try:
        dt_local = parse_user_time(right, user["timezone_name"])
    except ValueError:
        return
    reminder_id = await create_reminder(message.from_user.id, left, dt_local.astimezone(timezone.utc).isoformat(), "work", "medium")
    await message.answer(f"✅ Быстрое напоминание создано. ID: {reminder_id}")
