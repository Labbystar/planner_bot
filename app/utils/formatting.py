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
    "sent": "Отправлено",
}


def compact_notification(text: str, when_local: datetime, priority: str, category: str) -> str:
    title = text.strip().replace("\n", " ")
    if len(title) > 42:
        title = title[:39] + "..."
    return (
        f"⏰ {title}\n"
        f"📅 {when_local.strftime('%d.%m %H:%M')} · {PRIORITY_LABELS.get(priority, priority)} · {CATEGORY_LABELS.get(category, category)}"
    )


def reminder_card(reminder: dict, when_local: datetime) -> str:
    note = f"\n📝 {escape(reminder['note'])}" if reminder.get("note") else ""
    return (
        f"<b>⏰ {escape(reminder['text'])}</b>\n\n"
        f"📅 {when_local.strftime('%d.%m.%Y %H:%M')}\n"
        f"{CATEGORY_LABELS.get(reminder['category'], reminder['category'])}\n"
        f"{PRIORITY_LABELS.get(reminder['priority'], reminder['priority'])}\n"
        f"📌 Статус: {STATUS_LABELS.get(reminder['status'], reminder['status'])}"
        f"{note}"
    )


def page_header(title: str, page: int, total_pages: int) -> str:
    return f"<b>{title}</b>\nСтраница {page}/{total_pages}"
