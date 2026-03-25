from aiogram import Router, F
from aiogram.types import Message

from app.keyboards.menu import employee_stats_menu, team_menu
from app.services.reminders import list_all_reminders
from app.services.users import list_users

router = Router()


def _user_label(user: dict) -> str:
    return user.get("full_name") or (f"@{user['username']}" if user.get("username") else f"ID {user['user_id']}")


@router.message(F.text == "📊 Статистика по сотрудникам")
async def employee_stats_root(message: Message) -> None:
    await message.answer(
        "📊 Статистика по сотрудникам\n\nВыбери раздел:",
        reply_markup=employee_stats_menu(),
    )


@router.message(F.text == "⬅️ Назад в команду")
async def back_to_team(message: Message) -> None:
    await message.answer("📊 Раздел команды", reply_markup=team_menu())


@router.message(F.text == "📌 Нагрузка")
async def load_stats(message: Message) -> None:
    users = await list_users()
    lines = ["📌 Нагрузка по сотрудникам", ""]
    for u in users:
        reminders = await list_all_reminders(u["user_id"])
        active = [
            r for r in reminders
            if r.get("status") in ("active", "in_progress", "pending_confirmation", "overdue", "snoozed")
        ]
        lines.append(f"{_user_label(u)} — {len(active)}")
    await message.answer("\n".join(lines), reply_markup=employee_stats_menu())


@router.message(F.text == "📈 Общая статистика")
async def general_stats(message: Message) -> None:
    users = await list_users()
    total_done = 0
    total_overdue = 0
    total_pending = 0
    total_time_seconds = 0
    total_time_count = 0

    for u in users:
        reminders = await list_all_reminders(u["user_id"])
        for r in reminders:
            status = r.get("status")
            if status == "confirmed":
                total_done += 1
            if status == "overdue":
                total_overdue += 1
            if status == "pending_confirmation":
                total_pending += 1

            created_at = r.get("created_at")
            completed_at = r.get("completed_at")
            if created_at and completed_at:
                try:
                    from datetime import datetime
                    start = datetime.fromisoformat(created_at)
                    end = datetime.fromisoformat(completed_at)
                    delta = (end - start).total_seconds()
                    if delta >= 0:
                        total_time_seconds += delta
                        total_time_count += 1
                except Exception:
                    pass

    if total_time_count:
        avg_minutes = int(total_time_seconds // total_time_count // 60)
        avg_text = f"{avg_minutes} мин"
    else:
        avg_text = "н/д"

    text = (
        "📈 Общая статистика\n\n"
        f"Выполнено: {total_done}\n"
        f"Просрочено: {total_overdue}\n"
        f"Ждут подтверждения: {total_pending}\n"
        f"Среднее время выполнения: {avg_text}"
    )
    await message.answer(text, reply_markup=employee_stats_menu())


@router.message(F.text == "🏆 Рейтинг")
async def rating(message: Message) -> None:
    users = await list_users()
    rows = []
    for u in users:
        reminders = await list_all_reminders(u["user_id"])
        relevant = [r for r in reminders if r.get("status") not in ("cancelled",)]
        total = len(relevant)
        confirmed = len([r for r in relevant if r.get("status") == "confirmed"])
        snoozed = len([r for r in relevant if r.get("status") == "snoozed"])
        overdue = len([r for r in relevant if r.get("status") == "overdue"])
        in_time_percent = int((confirmed / total) * 100) if total else 0
        rows.append((_user_label(u), in_time_percent, snoozed, overdue))

    rows.sort(key=lambda x: x[1], reverse=True)

    lines = ["🏆 Рейтинг сотрудников", ""]
    for idx, (label, percent, snoozed, overdue) in enumerate(rows, start=1):
        lines.append(f"{idx}. {label} — {percent}% в срок | ⏸ {snoozed} | 🔴 {overdue}")

    await message.answer("\n".join(lines), reply_markup=employee_stats_menu())
