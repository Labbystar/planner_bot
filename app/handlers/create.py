from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.create import assignee_kb, categories_kb, note_kb, priorities_kb
from app.keyboards.menu import main_menu
from app.services.reminders import create_reminder
from app.services.users import get_user, list_users
from app.utils.datetime_parser import parse_date_input, parse_time_input
from app.utils.formatting import CATEGORY_LABELS, PRIORITY_LABELS
from app.utils.time import parse_user_time

router = Router()


class CreateReminder(StatesGroup):
    text = State()
    category = State()
    priority = State()
    note = State()
    assignee = State()
    assignee_manual = State()
    time_input = State()
    date_input = State()


def render_user_label(user: dict | None, fallback_id: int | None = None) -> str:
    if user:
        if user.get("full_name"):
            return user["full_name"]
        if user.get("username"):
            return f"@{user['username']}"
        if user.get("user_id"):
            return f"ID {user['user_id']}"
    if fallback_id is not None:
        return f"ID {fallback_id}"
    return "Неизвестный пользователь"


async def send_assignment_notification(
    message: Message,
    assigned_user_id: int,
    owner_user_id: int,
    text: str,
    dt_local,
    category: str,
    priority: str,
    note: str | None,
) -> None:
    if assigned_user_id == owner_user_id:
        return

    owner_user = await get_user(owner_user_id)
    owner_label = render_user_label(owner_user, owner_user_id)

    lines = [
        "📥 Вам поставлена задача",
        "",
        f"📌 {text}",
        f"📅 Срок: {dt_local.strftime('%d.%m.%Y %H:%M')}",
        f"🚦 Приоритет: {PRIORITY_LABELS.get(priority, priority)}",
        f"{CATEGORY_LABELS.get(category, category)}",
        f"👤 Постановщик: {owner_label}",
    ]
    if note:
        lines.append(f"📝 Комментарий: {note}")

    try:
        await message.bot.send_message(assigned_user_id, "\n".join(lines))
    except Exception:
        # Не валим создание задачи, если не удалось отправить уведомление исполнителю
        pass


@router.message(F.text == "➕ Создать")
async def start_create(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CreateReminder.text)
    await message.answer("<b>Шаг 1/7</b>\nНапиши короткий текст задачи.", parse_mode="HTML")


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
    await message.answer("<b>Шаг 2/7</b>\nВыбери категорию.", reply_markup=categories_kb(), parse_mode="HTML")


@router.callback_query(CreateReminder.category, F.data.startswith("cat:"))
async def got_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(category=callback.data.split(":", 1)[1])
    await state.set_state(CreateReminder.priority)
    await callback.message.answer("<b>Шаг 3/7</b>\nВыбери приоритет.", reply_markup=priorities_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(CreateReminder.priority, F.data.startswith("prio:"))
async def got_priority(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(priority=callback.data.split(":", 1)[1])
    await state.set_state(CreateReminder.note)
    await callback.message.answer(
        "<b>Шаг 4/7</b>\nДобавь заметку к задаче или пропусти шаг.",
        parse_mode="HTML",
        reply_markup=note_kb(),
    )
    await callback.answer()


@router.callback_query(CreateReminder.note, F.data == "note:skip")
async def skip_note(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(note=None)
    await state.set_state(CreateReminder.assignee)
    users = await list_users(exclude_user_id=callback.from_user.id)
    await callback.message.answer(
        "<b>Шаг 5/7</b>\nКому делегировать задачу? По умолчанию можно назначить себе.",
        parse_mode="HTML",
        reply_markup=assignee_kb(users, callback.from_user.id),
    )
    await callback.answer()


@router.message(CreateReminder.note)
async def got_note(message: Message, state: FSMContext) -> None:
    await state.update_data(note=message.text.strip())
    await state.set_state(CreateReminder.assignee)
    users = await list_users(exclude_user_id=message.from_user.id)
    await message.answer(
        "<b>Шаг 5/7</b>\nКому делегировать задачу? По умолчанию можно назначить себе.",
        parse_mode="HTML",
        reply_markup=assignee_kb(users, message.from_user.id),
    )


@router.callback_query(CreateReminder.assignee, F.data.startswith("assign:"))
async def got_assignee(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await state.set_state(CreateReminder.assignee_manual)
        await callback.message.answer("Введи Telegram ID пользователя бота, которому нужно делегировать задачу.")
        await callback.answer()
        return
    await state.update_data(assigned_user_id=int(value))
    await state.set_state(CreateReminder.time_input)
    await callback.message.answer(
        "<b>Шаг 6/7</b>\nУкажи время уведомления.\n\n"
        "Поддерживаются форматы:\n"
        "• <code>13:45</code>\n"
        "• <code>13-45</code>\n"
        "• <code>13.45</code>\n"
        "• <code>13 45</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(CreateReminder.assignee_manual)
async def got_assignee_manual(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("Нужен числовой Telegram ID.")
        return
    user = await get_user(int(message.text))
    if not user:
        await message.answer("Этот пользователь ещё не запускал бота. Попроси его сначала нажать /start.")
        return
    await state.update_data(assigned_user_id=int(message.text))
    await state.set_state(CreateReminder.time_input)
    await message.answer(
        "<b>Шаг 6/7</b>\nУкажи время уведомления.\n\n"
        "Поддерживаются форматы:\n"
        "• <code>13:45</code>\n"
        "• <code>13-45</code>\n"
        "• <code>13.45</code>\n"
        "• <code>13 45</code>",
        parse_mode="HTML",
    )


@router.message(CreateReminder.time_input)
async def got_time_input(message: Message, state: FSMContext) -> None:
    parsed = parse_time_input(message.text)
    if not parsed:
        await message.answer(
            "Не понял время.\n\n"
            "Попробуй так:\n"
            "• <code>13:45</code>\n"
            "• <code>13-45</code>\n"
            "• <code>13.45</code>\n"
            "• <code>13 45</code>",
            parse_mode="HTML",
        )
        return

    hour, minute = parsed
    await state.update_data(input_hour=hour, input_minute=minute)
    await state.set_state(CreateReminder.date_input)
    await message.answer(
        "<b>Шаг 7/7</b>\nУкажи дату уведомления.\n\n"
        "Поддерживаются форматы:\n"
        "• <code>25.03.26</code>\n"
        "• <code>25-03-26</code>\n"
        "• <code>25 03 26</code>",
        parse_mode="HTML",
    )


@router.message(CreateReminder.date_input)
async def got_date_input(message: Message, state: FSMContext) -> None:
    parsed_date = parse_date_input(message.text)
    if not parsed_date:
        await message.answer(
            "Не понял дату.\n\n"
            "Попробуй так:\n"
            "• <code>25.03.26</code>\n"
            "• <code>25-03-26</code>\n"
            "• <code>25 03 26</code>",
            parse_mode="HTML",
        )
        return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start")
        return

    data = await state.get_data()
    hour = int(data.get("input_hour", 9))
    minute = int(data.get("input_minute", 0))

    dt_local = parsed_date.replace(hour=hour, minute=minute)
    assigned_user_id = int(data.get("assigned_user_id") or message.from_user.id)

    reminder_id = await create_reminder(
        owner_user_id=message.from_user.id,
        assigned_user_id=assigned_user_id,
        text=data["text"],
        scheduled_at_utc=dt_local.astimezone(timezone.utc).isoformat(),
        category=data["category"],
        priority=data["priority"],
        note=data.get("note"),
    )

    assigned_user = await get_user(assigned_user_id)
    assigned_label = render_user_label(assigned_user, assigned_user_id)

    await send_assignment_notification(
        message=message,
        assigned_user_id=assigned_user_id,
        owner_user_id=message.from_user.id,
        text=data["text"],
        dt_local=dt_local,
        category=data["category"],
        priority=data["priority"],
        note=data.get("note"),
    )

    await state.clear()
    await message.answer(
        "✅ Задача создана\n"
        f"📌 {data['text']}\n"
        f"📅 {dt_local.strftime('%d.%m.%Y %H:%M')}\n"
        f"👤 Назначено: {assigned_label}",
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
    reminder_id = await create_reminder(
        message.from_user.id,
        message.from_user.id,
        left,
        dt_local.astimezone(timezone.utc).isoformat(),
        "work",
        "medium",
    )
    await message.answer(f"✅ Быстрое напоминание создано. ID: {reminder_id}")
