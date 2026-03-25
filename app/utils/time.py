from __future__ import annotations

import re
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


def _next_or_today(now_local: datetime, hour: int, minute: int) -> datetime:
    candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate


def parse_user_time(raw: str, tz_name: str) -> datetime:
    text = re.sub(r"\s+", " ", raw.strip().lower())
    now_local = datetime.now(ZoneInfo(tz_name)).replace(second=0, microsecond=0)

    # absolute full datetime
    for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=ZoneInfo(tz_name))
        except ValueError:
            pass

    # today/tomorrow/day after tomorrow
    day_shift = None
    if text.startswith('сегодня'):
        day_shift = 0
        hm_text = text.replace('сегодня', '', 1).strip()
    elif text.startswith('завтра'):
        day_shift = 1
        hm_text = text.replace('завтра', '', 1).strip()
    elif text.startswith('послезавтра'):
        day_shift = 2
        hm_text = text.replace('послезавтра', '', 1).strip()
    else:
        hm_text = None

    if day_shift is not None:
        hm_text = hm_text.removeprefix('в').strip()
        if not hm_text:
            hour, minute = 9, 0
        elif ':' in hm_text:
            hour, minute = map(int, hm_text.split(':', 1))
        else:
            hour, minute = int(hm_text), 0
        return (now_local + timedelta(days=day_shift)).replace(hour=hour, minute=minute, second=0, microsecond=0)

    # relative expressions
    if text.startswith('через '):
        rest = text[6:].strip()
        if rest in {'час', '1 час', 'один час'}:
            return now_local + timedelta(hours=1)
        if rest in {'пол часа', 'полчаса', '30 минут', '30 мин'}:
            return now_local + timedelta(minutes=30)
        if rest in {'полтора часа', '1.5 часа'}:
            return now_local + timedelta(minutes=90)

        hours = 0
        minutes = 0
        m = re.search(r'(\d+)\s*(час|часа|часов|ч)', rest)
        if m:
            hours = int(m.group(1))
        m = re.search(r'(\d+)\s*(минута|минуты|минут|мин|м)', rest)
        if m:
            minutes = int(m.group(1))
        if hours or minutes:
            return now_local + timedelta(hours=hours, minutes=minutes)

    # plain time: today if future, else tomorrow
    if re.fullmatch(r'\d{1,2}:\d{2}', text):
        hour, minute = map(int, text.split(':', 1))
        return _next_or_today(now_local, hour, minute)
    if re.fullmatch(r'\d{1,2}', text):
        return _next_or_today(now_local, int(text), 0)
    if text.startswith('в '):
        hm = text[2:].strip()
        if re.fullmatch(r'\d{1,2}:\d{2}', hm):
            hour, minute = map(int, hm.split(':', 1))
            return _next_or_today(now_local, hour, minute)
        if re.fullmatch(r'\d{1,2}', hm):
            return _next_or_today(now_local, int(hm), 0)

    raise ValueError('Unsupported date/time format')
