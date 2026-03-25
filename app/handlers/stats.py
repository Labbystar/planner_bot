
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.services.reminders import list_all_reminders
from app.services.users import list_users

router = Router()

@router.message(F.text == "📊 Статистика по сотрудникам")
async def stats_menu(message: Message):
    await message.answer(
        "📊 Статистика по сотрудникам\n\nВыбери раздел:",
        reply_markup=None
    )

@router.message(F.text == "📌 Нагрузка")
async def load_stats(message: Message):
    users = await list_users()
    text = "📌 Нагрузка\n\n"
    for u in users:
        reminders = await list_all_reminders(u["user_id"])
        active = [r for r in reminders if r["status"] in ("active","in_progress","pending_confirmation")]
        text += f"{u.get('full_name') or u.get('username') or u['user_id']} — {len(active)}\n"
    await message.answer(text)

@router.message(F.text == "📈 Общая статистика")
async def general_stats(message: Message):
    reminders = await list_all_reminders(message.from_user.id)
    done = len([r for r in reminders if r["status"] == "confirmed"])
    overdue = len([r for r in reminders if r["status"] == "overdue"])
    await message.answer(f"📈 Статистика\n\nВыполнено: {done}\nПросрочено: {overdue}")

@router.message(F.text == "🏆 Рейтинг")
async def rating(message: Message):
    users = await list_users()
    text = "🏆 Рейтинг\n\n"
    for u in users:
        reminders = await list_all_reminders(u["user_id"])
        total = len(reminders)
        done = len([r for r in reminders if r["status"] == "confirmed"])
        percent = int((done/total)*100) if total else 0
        text += f"{u.get('full_name') or u.get('username') or u['user_id']} — {percent}%\n"
    await message.answer(text)
