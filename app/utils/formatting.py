from __future__ import annotations

from datetime import datetime
from html import escape

PRIORITY_LABELS = {
    "low": "🟢 Низкий",
    "medium": "🟡 Средний",
    "high": "🔴 Высокий",
}

CATEGORY_LABELS = {
    "work": "📂 Работа",
    "personal": "📂 Личное",
    "finance": "📂 Финансы",
    "important": "📂 Важное",
}

STATUS_LABELS = {
    "active": "Активно",
    "done": "Выполнено",
    "snoozed": "Отложено",
    "sent": "Ждет подтверждения",
}

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def compact_notification(text: str, when_local: datetime, priority: str, category: str, note: str | None = None) -> str:
    title = text.strip().replace("\n", " ")
    if len(title) > 42:
        title = title[:39] + "..."
    note_line = ""
    if note:
        compact = note.strip().replace("\n", " ")
        if len(compact) > 36:
            compact = compact[:33] + "..."
        note_line = f"\n📝 {compact}"
    return (
        f"⏰ {title}{note_line}\n"
        f"📅 {when_local.strftime('%d.%m %H:%M')} · {PRIORITY_LABELS.get(priority, priority)} · {CATEGORY_LABELS.get(category, category)}"
    )


def reminder_card(reminder: dict, when_local: datetime) -> str:
    note = f"\n📝 {escape(reminder['note'])}" if reminder.get("note") else ""
    status = STATUS_LABELS.get(reminder["status"], reminder["status"])
    delegated = ""
    if reminder.get("assigned_user_id") and reminder.get("assigned_user_id") != reminder.get("owner_user_id"):
        delegated = f"\n👤 Делегировано: ID {reminder['assigned_user_id']}"
    return (
        f"<b>⏰ {escape(reminder['text'])}</b>\n\n"
        f"📅 {when_local.strftime('%d.%m.%Y %H:%M')}\n"
        f"{CATEGORY_LABELS.get(reminder['category'], reminder['category'])} · {PRIORITY_LABELS.get(reminder['priority'], reminder['priority'])}\n"
        f"📌 Статус: {status}{delegated}{note}"
    )


def page_header(title: str, page: int, total_pages: int, subtitle: str | None = None) -> str:
    base = f"<b>{title}</b>\nСтраница {page}/{total_pages}"
    if subtitle:
        base += f"\n{subtitle}"
    return base


def list_line(reminder: dict, when_local: datetime) -> str:
    delegated = ""
    if reminder.get("assigned_user_id") and reminder.get("assigned_user_id") != reminder.get("owner_user_id"):
        delegated = f"\n  👤 ID {reminder['assigned_user_id']}"
    return (
        f"• <b>{when_local.strftime('%d.%m %H:%M')}</b> — {escape(reminder['text'])}\n"
        f"  {CATEGORY_LABELS.get(reminder['category'], reminder['category'])} · {PRIORITY_LABELS.get(reminder['priority'], reminder['priority'])}{delegated}"
    )


def stats_text(stats: dict) -> str:
    status_lines = [f"• {STATUS_LABELS.get(k, k)}: {v}" for k, v in sorted(stats['by_status'].items())]
    category_lines = [f"• {CATEGORY_LABELS.get(k, k)}: {v}" for k, v in sorted(stats['by_category'].items())]
    priority_lines = [f"• {PRIORITY_LABELS.get(k, k)}: {v}" for k, v in sorted(stats.get('by_priority', {}).items())]
    return (
        f"<b>📊 Статистика</b>\n\n"
        f"Всего задач: <b>{stats['total']}</b>\n\n"
        f"<b>По статусам</b>\n" + ("\n".join(status_lines) if status_lines else "Пока пусто") +
        f"\n\n<b>По категориям</b>\n" + ("\n".join(category_lines) if category_lines else "Пока пусто") +
        f"\n\n<b>По приоритетам</b>\n" + ("\n".join(priority_lines) if priority_lines else "Пока пусто")
    )


def calendar_title(year: int, month: int) -> str:
    return f"<b>🗓 Календарь</b>\n{MONTHS_RU.get(month, month)} {year}"
