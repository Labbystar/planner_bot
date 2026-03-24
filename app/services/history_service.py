import json
from datetime import datetime

from app.repositories.events import EventsRepo


class HistoryService:
    def __init__(self, events_repo: EventsRepo):
        self.events_repo = events_repo

    async def log(self, reminder_id: int, user_id: int, event_type: str, payload: dict | None = None) -> None:
        raw = json.dumps(payload, ensure_ascii=False) if payload else None
        await self.events_repo.add_event(reminder_id, user_id, event_type, raw)

    async def render_user_history(self, user_id: int, limit: int = 20) -> str:
        events = await self.events_repo.list_events_for_user(user_id, limit)
        if not events:
            return "История пока пуста."

        lines: list[str] = []
        labels = {
            "created": "создано",
            "sent": "отправлено",
            "pre_sent": "предупреждение заранее",
            "done": "выполнено",
            "snoozed": "отложено",
            "deleted": "удалено",
            "share_created": "создана share-ссылка",
            "share_accepted": "принята share-ссылка",
            "missed": "пропущено",
            "acknowledged": "подтверждено",
            "skipped": "пропущено по правилам",
        }
        for event in events:
            dt = datetime.fromisoformat(event.created_at).strftime("%d.%m %H:%M")
            lines.append(f"{dt} — reminder #{event.reminder_id}: {labels.get(event.event_type, event.event_type)}")
        return "Последние события:\n\n" + "\n".join(lines)
