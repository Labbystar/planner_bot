from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.create import assignee_kb, categories_kb, note_kb, priorities_kb
from app.keyboards.menu import main_menu
from app.keyboards.reminders import assignee_actions
from app.services.reminders import create_attachment, create_reminder, count_attachments, get_reminder, list_attachments
from app.services.users import get_user, list_users
from app.utils.formatting import assignment_notification, user_label
from app.utils.time import parse_user_time, to_local

router = Router()


class CreateReminder(StatesGroup):
    text = State()
    category = State()
    priority = State()
    note = State()
    assignee = State()
    assignee_manual = State()
    when = State()


async def _go_to_assignee(message_or_callback, state: FSMContext, user_id: int):
    await state.set_state(CreateReminder.assignee)
    users = await list_users(exclude_user_id=user_id)
    text = (
        "<b>Шаг 5/6</b>\n"
        "Кому делегировать задачу?"
    )
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(text, parse_mode="HTML", reply_markup=assignee_kb(users, user_id))
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=assignee_kb(users, user_id))


@router.message(F.text == "➕ Создать")
async def start_create(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CreateReminder.text)
    await state.update_data(attachments=[])
    await message.answer("<b>Шаг 1/6</b>\nНапиши короткий текст задачи.", parse_mode="HTML")


@router.message(F.text == "⚡ Быстро")
async def quick_create_hint(message: Message) -> None:
    await message.answer(
        "Отправь одной строкой:\n<code>Текст | завтра в 9</code>\n\n"
        "Поддерживается:\n"
        "• через час\n• через 30 минут\n• 11:30\n• сегодня в 13:00\n• завтра в 9\n• 25.03.2026 14:45",
        parse_mode="HTML",
    )


@router.message(CreateReminder.text)
async def got_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text.strip())
    await state.set_state(CreateReminder.category)
    await message.answer("<b>Шаг 2/6</b>\nВыбери категорию.", reply_markup=categories_kb(), parse_mode="HTML")


@router.callback_query(CreateReminder.category, F.data.startswith("cat:"))
async def got_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(category=callback.data.split(":", 1)[1])
    await state.set_state(CreateReminder.priority)
    await callback.message.answer("<b>Шаг 3/6</b>\nВыбери приоритет.", reply_markup=priorities_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(CreateReminder.priority, F.data.startswith("prio:"))
async def got_priority(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(priority=callback.data.split(":", 1)[1])
    await state.set_state(CreateReminder.note)
    await callback.message.answer(
        "<b>Шаг 4/6</b>\n"
        "Добавь материалы к задаче или пропусти шаг.\n\n"
        "Можно отправить:\n"
        "• текст\n• фото\n• документ / таблицу\n• голосовое\n• ссылку\n\n"
        "Когда закончишь — нажми <b>Готово с вложениями</b>.",
        parse_mode="HTML",
        reply_markup=note_kb(),
    )
    await callback.answer()


@router.callback_query(CreateReminder.note, F.data == "note:skip")
async def skip_note(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(note=None, attachments=[])
    await _go_to_assignee(callback, state, callback.from_user.id)


@router.callback_query(CreateReminder.note, F.data == "note:done")
async def done_attachments(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    attachments = data.get("attachments", [])
    note = None
    for item in attachments:
        if item.get("attachment_type") == "text":
            note = item.get("text_value")
            break
    await state.update_data(note=note)
    await _go_to_assignee(callback, state, callback.from_user.id)


@router.message(CreateReminder.note, F.photo)
async def attach_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    attachments = data.get("attachments", [])
    photo = message.photo[-1]
    attachments.append({
        "attachment_type": "photo",
        "telegram_file_id": photo.file_id,
        "file_name": f"photo_{len(attachments)+1}.jpg",
        "mime_type": "image/jpeg",
        "text_value": None,
        "url_value": None,
    })
    await state.update_data(attachments=attachments)
    await message.answer(f"✅ Фото добавлено. Всего вложений: {len(attachments)}", reply_markup=note_kb())


@router.message(CreateReminder.note, F.document)
async def attach_document(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    attachments = data.get("attachments", [])
    doc = message.document
    attachments.append({
        "attachment_type": "document",
        "telegram_file_id": doc.file_id,
        "file_name": doc.file_name,
        "mime_type": doc.mime_type,
        "text_value": None,
        "url_value": None,
    })
    await state.update_data(attachments=attachments)
    await message.answer(f"✅ Файл добавлен. Всего вложений: {len(attachments)}", reply_markup=note_kb())


@router.message(CreateReminder.note, F.voice)
async def attach_voice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    attachments = data.get("attachments", [])
    voice = message.voice
    attachments.append({
        "attachment_type": "voice",
        "telegram_file_id": voice.file_id,
        "file_name": "voice.ogg",
        "mime_type": voice.mime_type,
        "text_value": None,
        "url_value": None,
    })
    await state.update_data(attachments=attachments)
    await message.answer(f"✅ Голосовое добавлено. Всего вложений: {len(attachments)}", reply_markup=note_kb())


@router.message(CreateReminder.note, F.audio)
async def attach_audio(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    attachments = data.get("attachments", [])
    audio = message.audio
    attachments.append({
        "attachment_type": "audio",
        "telegram_file_id": audio.file_id,
        "file_name": audio.file_name or "audio.mp3",
        "mime_type": audio.mime_type,
        "text_value": None,
        "url_value": None,
    })
    await state.update_data(attachments=attachments)
    await message.answer(f"✅ Аудио добавлено. Всего вложений: {len(attachments)}", reply_markup=note_kb())


@router.message(CreateReminder.note, F.text)
async def attach_text_or_link(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    data = await state.get_data()
    attachments = data.get("attachments", [])
    if text.lower().startswith(("http://", "https://")):
        attachments.append({
            "attachment_type": "link",
            "telegram_file_id": None,
            "file_name": None,
            "mime_type": None,
            "text_value": None,
            "url_value": text,
        })
        label = "Ссылка"
    else:
        attachments.append({
            "attachment_type": "text",
            "telegram_file_id": None,
            "file_name": None,
            "mime_type": None,
            "text_value": text,
            "url_value": None,
        })
        label = "Текст"
    await state.update_data(attachments=attachments)
    await message.answer(f"✅ {label} добавлен. Всего вложений: {len(attachments)}", reply_markup=note_kb())


@router.callback_query(CreateReminder.assignee, F.data.startswith("assign:"))
async def got_assignee(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await state.set_state(CreateReminder.assignee_manual)
        await callback.message.answer("Введи Telegram ID пользователя бота, которому нужно делегировать задачу.")
        await callback.answer()
        return
    await state.update_data(assigned_user_id=int(value))
    await state.set_state(CreateReminder.when)
    await callback.message.answer(
        "<b>Шаг 6/6</b>\nКогда прислать уведомление?\n\n"
        "Можно написать:\n"
        "• <code>через час</code>\n"
        "• <code>через 30 минут</code>\n"
        "• <code>11:30</code>\n"
        "• <code>сегодня в 13:00</code>\n"
        "• <code>завтра в 9</code>\n"
        "• <code>25.03.2026 14:45</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(CreateReminder.assignee_manual)
async def got_assignee_manual(message: Message, state: FSMContext) -> None:
    if not (message.text or '').isdigit():
        await message.answer("Нужен числовой Telegram ID.")
        return
    user = await get_user(int(message.text))
    if not user:
        await message.answer("Этот пользователь ещё не запускал бота. Попроси его сначала нажать /start.")
        return
    await state.update_data(assigned_user_id=int(message.text))
    await state.set_state(CreateReminder.when)
    await message.answer(
        "<b>Шаг 6/6</b>\nКогда прислать уведомление?\n\n"
        "Можно написать:\n"
        "• <code>через час</code>\n"
        "• <code>через 30 минут</code>\n"
        "• <code>11:30</code>\n"
        "• <code>сегодня в 13:00</code>\n"
        "• <code>завтра в 9</code>\n"
        "• <code>25.03.2026 14:45</code>",
        parse_mode="HTML",
    )


async def _send_attachments(bot, user_id: int, reminder_id: int) -> None:
    attachments = await list_attachments(reminder_id)
    if not attachments:
        return
    await bot.send_message(user_id, f"📎 К задаче прикреплены материалы: {len(attachments)}")
    for att in attachments:
        atype = att['attachment_type']
        if atype == 'photo' and att.get('telegram_file_id'):
            await bot.send_photo(user_id, att['telegram_file_id'])
        elif atype == 'document' and att.get('telegram_file_id'):
            await bot.send_document(user_id, att['telegram_file_id'])
        elif atype == 'voice' and att.get('telegram_file_id'):
            await bot.send_voice(user_id, att['telegram_file_id'])
        elif atype == 'audio' and att.get('telegram_file_id'):
            await bot.send_audio(user_id, att['telegram_file_id'])
        elif atype == 'text' and att.get('text_value'):
            await bot.send_message(user_id, f"📝 {att['text_value']}")
        elif atype == 'link' and att.get('url_value'):
            await bot.send_message(user_id, f"🔗 {att['url_value']}")


@router.message(CreateReminder.when)
async def got_when(message: Message, state: FSMContext) -> None:
    creator = await get_user(message.from_user.id)
    if not creator:
        await message.answer("Сначала нажми /start")
        return
    try:
        dt_local = parse_user_time(message.text, creator["timezone_name"])
    except ValueError:
        await message.answer(
            "Не понял дату/время. Попробуй: <code>через час</code>, <code>11:30</code>, <code>сегодня в 13:00</code>, <code>завтра в 9</code> или <code>25.03.2026 14:45</code>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    assigned_user_id = int(data.get("assigned_user_id") or message.from_user.id)
    reminder_id = await create_reminder(message.from_user.id, assigned_user_id, data["text"], dt_local.astimezone(timezone.utc).isoformat(), data["category"], data["priority"], data.get("note"))
    attachments = data.get('attachments', [])
    for item in attachments:
        await create_attachment(reminder_id, message.from_user.id, **item)
    await state.clear()
    assignee = await get_user(assigned_user_id)
    delegated = "себе" if assigned_user_id == message.from_user.id else user_label(assignee, assigned_user_id)
    await message.answer(f"✅ Задача создана. ID: {reminder_id}\n📅 {dt_local.strftime('%d.%m.%Y %H:%M')}\n👤 Назначено: {delegated}", reply_markup=main_menu())

    if assigned_user_id != message.from_user.id and assignee:
        reminder = await get_reminder(reminder_id)
        local_for_assignee = to_local(dt_local.astimezone(timezone.utc), assignee['timezone_name'])
        await message.bot.send_message(
            assigned_user_id,
            assignment_notification(reminder, local_for_assignee, user_label(creator, creator['user_id']), attachments_count=len(attachments)),
            parse_mode='HTML',
            reply_markup=assignee_actions(reminder_id),
        )
        await _send_attachments(message.bot, assigned_user_id, reminder_id)


@router.message(F.text.contains("|"))
async def quick_create(message: Message) -> None:
    creator = await get_user(message.from_user.id)
    if not creator:
        return
    left, right = [x.strip() for x in message.text.split("|", 1)]
    try:
        dt_local = parse_user_time(right, creator["timezone_name"])
    except ValueError:
        return
    reminder_id = await create_reminder(message.from_user.id, message.from_user.id, left, dt_local.astimezone(timezone.utc).isoformat(), "work", "medium")
    await message.answer(f"✅ Быстрая задача создана. ID: {reminder_id}")
