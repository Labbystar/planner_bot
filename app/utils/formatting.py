from __future__ import annotations

from datetime import datetime
from html import escape

PRIORITY_LABELS = {
    'low': '🟢 Низкий',
    'medium': '🟡 Средний',
    'high': '🔴 Высокий',
}

CATEGORY_LABELS = {
    'work': '📂 Работа',
    'personal': '📂 Личное',
    'finance': '📂 Финансы',
    'important': '📂 Важное',
}

STATUS_LABELS = {
    'active': 'Назначено',
    'in_progress': '🟡 В работе',
    'pending_confirmation': '🟢 Выполнено (ждёт подтверждения)',
    'confirmed': '🔵 Подтверждено',
    'overdue': '🔴 Просрочено',
    'snoozed': '⏸ Отложено',
    'cancelled': 'Отменено',
}

MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
    7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь',
}


def user_label(user: dict | None, fallback_id: int | None = None) -> str:
    if user:
        if user.get('username'):
            return '@' + user['username']
        if user.get('full_name'):
            return user['full_name']
    return f'ID {fallback_id}' if fallback_id else '—'


def compact_notification(text: str, when_local: datetime, priority: str, category: str, note: str | None = None) -> str:
    title = text.strip().replace('\n', ' ')
    if len(title) > 42:
        title = title[:39] + '...'
    note_line = ''
    if note:
        compact = note.strip().replace('\n', ' ')
        if len(compact) > 36:
            compact = compact[:33] + '...'
        note_line = f'\n📝 {compact}'
    return (
        f'⏰ {title}{note_line}\n'
        f'📅 {when_local.strftime("%d.%m %H:%M")} · {PRIORITY_LABELS.get(priority, priority)} · {CATEGORY_LABELS.get(category, category)}'
    )


def assignment_notification(reminder: dict, when_local: datetime, owner_label: str, attachments_count: int = 0) -> str:
    note = ''
    if reminder.get('note'):
        compact = str(reminder['note']).strip().replace('\n', ' ')
        if len(compact) > 50:
            compact = compact[:47] + '...'
        note = f'\n📝 {escape(compact)}'
    attach_line = f'\n📎 Вложений: {attachments_count}' if attachments_count else ''
    return (
        f'<b>📥 Вам поставлена задача</b>\n\n'
        f'📌 {escape(reminder["text"])}\n'
        f'📅 Срок: {when_local.strftime("%d.%m.%Y %H:%M")}\n'
        f'🚦 Приоритет: {PRIORITY_LABELS.get(reminder["priority"], reminder["priority"])}\n'
        f'📂 Категория: {CATEGORY_LABELS.get(reminder["category"], reminder["category"])}\n'
        f'👤 Постановщик: {escape(owner_label)}{note}{attach_line}'
    )


def owner_status_notification(reminder: dict, actor_label: str, action_text: str, comment: str | None = None) -> str:
    msg = (
        f'<b>📣 Обновление по задаче</b>\n\n'
        f'📌 {escape(reminder["text"])}\n'
        f'👤 Исполнитель: {escape(actor_label)}\n'
        f'📍 Статус: {escape(action_text)}'
    )
    if comment:
        msg += f'\n💬 Комментарий: {escape(comment)}'
    return msg


def owner_confirmation_notification(reminder: dict, actor_label: str) -> str:
    return (
        f'<b>📣 Исполнитель отметил задачу как выполненную</b>\n\n'
        f'📌 {escape(reminder["text"])}\n'
        f'👤 Исполнитель: {escape(actor_label)}\n'
        f'📍 Статус: 🟢 Выполнено (ждёт подтверждения)'
    )


def assignee_feedback_notification(reminder: dict, action_text: str) -> str:
    return (
        f'<b>{escape(action_text)}</b>\n\n'
        f'📌 {escape(reminder["text"])}\n'
        f'📍 Статус: {STATUS_LABELS.get(reminder.get("status"), reminder.get("status", "—"))}'
    )


def overdue_notification(reminder: dict, role: str) -> str:
    title = '⛔ Задача просрочена' if role == 'assignee' else '⚠ Задача просрочена'
    return (
        f'<b>{title}</b>\n\n'
        f'📌 {escape(reminder["text"])}\n'
        f'📍 Статус: {STATUS_LABELS.get("overdue")}'
    )


def reminder_card(reminder: dict, when_local: datetime, owner_label: str | None = None, assignee_label: str | None = None, mode: str = 'shared') -> str:
    note = f'\n📝 {escape(reminder["note"])}' if reminder.get('note') else ''
    assignee_comment = f'\n💬 Комментарий исполнителя: {escape(reminder["assignee_comment"])}' if reminder.get('assignee_comment') else ''
    attachments = f'\n📎 Вложений: {int(reminder.get("attachments_count", 0))}' if reminder.get('attachments_count') else ''
    comments_count = reminder.get('comments_count')
    comments_total = f'\n💬 Комментариев: {int(comments_count)}' if comments_count else ''
    status = STATUS_LABELS.get(reminder['status'], reminder['status'])
    participants = []
    if mode == 'owner':
        participants.append(f'👤 Исполнитель: {escape(assignee_label or "—")}')
    elif mode == 'assigned':
        participants.append(f'👤 Постановщик: {escape(owner_label or "—")}')
    else:
        if owner_label:
            participants.append(f'👤 Постановщик: {escape(owner_label)}')
        if assignee_label:
            participants.append(f'👥 Исполнитель: {escape(assignee_label)}')
    participant_block = ('\n' + '\n'.join(participants)) if participants else ''
    comments_history = ''
    if reminder.get('comments_preview'):
        comments_history = '\n\n<b>💬 Комментарии:</b>\n' + '\n'.join(reminder['comments_preview'])
    return (
        f'<b>📌 {escape(reminder["text"])}</b>\n\n'
        + f'📅 {when_local.strftime("%d.%m.%Y %H:%M")}\n'
        + f'{CATEGORY_LABELS.get(reminder["category"], reminder["category"])} · {PRIORITY_LABELS.get(reminder["priority"], reminder["priority"])}\n'
        + f'📌 Статус: {status}{participant_block}{note}{assignee_comment}{attachments}{comments_total}{comments_history}'
    )


def page_header(title: str, page: int, total_pages: int, subtitle: str | None = None) -> str:
    base = f'<b>{title}</b>\nСтраница {page}/{total_pages}'
    if subtitle:
        base += f'\n{subtitle}'
    return base


def list_line(reminder: dict, when_local: datetime, owner_label: str | None = None, assignee_label: str | None = None, mode: str = 'shared') -> str:
    detail = ''
    if mode == 'owner' and assignee_label:
        detail = f'\n  👤 Исполнитель: {escape(assignee_label)}'
    elif mode == 'assigned' and owner_label:
        detail = f'\n  👤 Постановщик: {escape(owner_label)}'
    attachments = f'\n  📎 Вложений: {int(reminder.get("attachments_count", 0))}' if reminder.get('attachments_count') else ''
    status = STATUS_LABELS.get(reminder['status'], reminder['status'])
    return (
        f'• <b>{when_local.strftime("%d.%m %H:%M")}</b> — {escape(reminder["text"])}\n'
        f'  {CATEGORY_LABELS.get(reminder["category"], reminder["category"])} · {PRIORITY_LABELS.get(reminder["priority"], reminder["priority"])} · {status}{detail}{attachments}'
    )


def stats_text(stats: dict) -> str:
    status_lines = [f'• {STATUS_LABELS.get(k, k)}: {v}' for k, v in sorted(stats['by_status'].items())]
    category_lines = [f'• {CATEGORY_LABELS.get(k, k)}: {v}' for k, v in sorted(stats['by_category'].items())]
    priority_lines = [f'• {PRIORITY_LABELS.get(k, k)}: {v}' for k, v in sorted(stats.get('by_priority', {}).items())]
    return (
        f'<b>📊 Статистика</b>\n\n'
        f'Всего задач: <b>{stats["total"]}</b>\n\n'
        f'<b>По статусам</b>\n' + ('\n'.join(status_lines) if status_lines else 'Пока пусто') +
        f'\n\n<b>По категориям</b>\n' + ('\n'.join(category_lines) if category_lines else 'Пока пусто') +
        f'\n\n<b>По приоритетам</b>\n' + ('\n'.join(priority_lines) if priority_lines else 'Пока пусто')
    )


def calendar_title(year: int, month: int) -> str:
    return f'<b>🗓 Календарь</b>\n{MONTHS_RU.get(month, month)} {year}'
