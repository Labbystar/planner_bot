from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"Unknown timezone: {name}") from e
    return name


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return now_utc().isoformat()


def to_local(dt_utc: datetime, tz_name: str) -> datetime:
    return dt_utc.astimezone(ZoneInfo(tz_name))


def parse_user_time(raw: str, tz_name: str) -> datetime:
    text = raw.strip().lower()
    now_local = datetime.now(ZoneInfo(tz_name)).replace(second=0, microsecond=0)

    if text.startswith("через ") and "час" in text:
        num = int(''.join(ch for ch in text if ch.isdigit()))
        return now_local + timedelta(hours=num)

    if text.startswith("через ") and ("мин" in text or "minute" in text):
        num = int(''.join(ch for ch in text if ch.isdigit()))
        return now_local + timedelta(minutes=num)

    if text.startswith("завтра"):
        hour = 9
        minute = 0
        if "в" in text:
            try:
                hm = text.split("в", 1)[1].strip()
                if ":" in hm:
                    hour, minute = map(int, hm.split(":"))
                else:
                    hour = int(hm)
            except Exception:
                pass
        return (now_local + timedelta(days=1)).replace(hour=hour, minute=minute)

    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=ZoneInfo(tz_name))
        except ValueError:
            pass

    if raw.strip().isdigit():
        hour = int(raw.strip())
        return now_local.replace(hour=hour, minute=0) if hour > now_local.hour else (now_local + timedelta(days=1)).replace(hour=hour, minute=0)

    if raw.strip().startswith("в "):
        hm = raw.strip()[2:]
        if ":" in hm:
            hour, minute = map(int, hm.split(":"))
        else:
            hour, minute = int(hm), 0
        return now_local.replace(hour=hour, minute=minute) if (hour, minute) > (now_local.hour, now_local.minute) else (now_local + timedelta(days=1)).replace(hour=hour, minute=minute)

    raise ValueError("Unsupported date/time format")
