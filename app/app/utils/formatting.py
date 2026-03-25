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
    "cancelled": "Отменено",
}

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def user_label(user: dict | None, fallback_id: int | None = None) -> str:
    if user:
        if user.get('username'):
            return '@' + user['username']
        if user.get('full_name'):
            return user['full_name']
    return f'ID {fallback_id}' if fallback_id else '—'


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


def assignment_notification(reminder: dict, when_local: datetime, owner_label: str) -> str:
    note = ""
    if reminder.get('note'):
        compact = str(reminder['note']).strip().replace("\n", " ")
        if len(compact) > 50:
            compact = compact[:47] + '...'
        note = f"\n📝 {escape(compact)}"
    return (
        f"<b>📥 Вам поставлена задача</b>\n\n"
        f"📌 {escape(reminder['text'])}\n"
        f"📅 Срок: {when_local.strftime('%d.%m.%Y %H:%M')}\n"
        f"🚦 Приоритет: {PRIORITY_LABELS.get(reminder['priority'], reminder['priority'])}\n"
        f"📂 Категория: {CATEGORY_LABELS.get(reminder['category'], reminder['category'])}\n"
        f"👤 Постановщик: {escape(owner_label)}{note}"
    )


def reminder_card(reminder: dict, when_local: datetime, owner_label: str | None = None, assignee_label: str | None = None, mode: str = 'shared') -> str:
    note = f"\n📝 {escape(reminder['note'])}" if reminder.get("note") else ""
    assignee_comment = f"\n💬 Комментарий: {escape(reminder['assignee_comment'])}" if reminder.get("assignee_comment") else ""
    status = STATUS_LABELS.get(reminder["status"], reminder["status"])
    participants = []
    if mode == 'owner':
        participants.append(f"👤 Исполнитель: {escape(assignee_label or '—')}")
    elif mode == 'assigned':
        participants.append(f"👤 Постановщик: {escape(owner_label or '—')}")
    else:
        if owner_label:
            participants.append(f"👤 Постановщик: {escape(owner_label)}")
        if assignee_label:
            participants.append(f"👥 Исполнитель: {escape(assignee_label)}")
    participant_block = ("\n" + "\n".join(participants)) if participants else ""
    return (
        f"<b>📌 {escape(reminder['text'])}</b>\n\n"
        f"📅 {when_local.strftime('%d.%m.%Y %H:%M')}\n"
        f"{CATEGORY_LABELS.get(reminder['category'], reminder['category'])} · {PRIORITY_LABELS.get(reminder['priority'], reminder['priority'])}\n"
        f"📌 Статус: {status}{participant_block}{note}{assignee_comment}"
    )


def page_header(title: str, page: int, total_pages: int, subtitle: str | None = None) -> str:
    base = f"<b>{title}</b>\nСтраница {page}/{total_pages}"
    if subtitle:
        base += f"\n{subtitle}"
    return base


def list_line(reminder: dict, when_local: datetime, owner_label: str | None = None, assignee_label: str | None = None, mode: str = 'shared') -> str:
    detail = ""
    if mode == 'owner' and assignee_label:
        detail = f"\n  👤 Исполнитель: {escape(assignee_label)}"
    elif mode == 'assigned' and owner_label:
        detail = f"\n  👤 Постановщик: {escape(owner_label)}"
    return (
        f"• <b>{when_local.strftime('%d.%m %H:%M')}</b> — {escape(reminder['text'])}\n"
        f"  {CATEGORY_LABELS.get(reminder['category'], reminder['category'])} · {PRIORITY_LABELS.get(reminder['priority'], reminder['priority'])}{detail}"
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
