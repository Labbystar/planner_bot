import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def normalize_recipients(raw: str) -> list[int]:
    result: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        result.append(int(item))
    return list(dict.fromkeys(result))


def parse_flexible_time(raw: str) -> str:
    value = raw.strip().lower().replace("в ", "", 1)
    for fmt in ("%H:%M", "%H"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%H:%M")
        except ValueError:
            pass
    raise ValueError("time")


def parse_smart_datetime(raw: str, tz_name: str, now: datetime | None = None) -> datetime:
    tz = ZoneInfo(tz_name)
    now = now or datetime.now(tz)
    s = " ".join(raw.strip().lower().split())

    # exact YYYY-MM-DD HH:MM
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=tz)
        except ValueError:
            pass

    # через N часов / минут
    m = re.fullmatch(r"через\s+(\d+)\s+(час|часа|часов|мин|минута|минуты|минут)", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = timedelta(hours=n) if unit.startswith("час") else timedelta(minutes=n)
        return (now + delta).replace(second=0, microsecond=0)

    # завтра в 9 / завтра в 09:30
    m = re.fullmatch(r"завтра(?:\s+в)?\s+(\d{1,2})(?::(\d{2}))?", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        target = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target

    # today/tomorrow english variants
    m = re.fullmatch(r"tomorrow(?:\s+at)?\s+(\d{1,2})(?::(\d{2}))?", s)
    if m:
        hour = int(m.group(1)); minute = int(m.group(2) or 0)
        return (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)

    weekdays = {
        "понедельник":0,"пн":0,"monday":0,"mon":0,
        "вторник":1,"вт":1,"tuesday":1,"tue":1,
        "среда":2,"ср":2,"wednesday":2,"wed":2,
        "четверг":3,"чт":3,"thursday":3,"thu":3,
        "пятница":4,"пт":4,"friday":4,"fri":4,
        "суббота":5,"сб":5,"saturday":5,"sat":5,
        "воскресенье":6,"вс":6,"sunday":6,"sun":6,
    }
    m = re.fullmatch(r"(?:в\s+)?([а-яa-z]+)(?:\s+в|\s+at)?\s+(\d{1,2})(?::(\d{2}))?", s)
    if m and m.group(1) in weekdays:
        target_wd = weekdays[m.group(1)]
        hour = int(m.group(2)); minute = int(m.group(3) or 0)
        days_ahead = (target_wd - now.weekday()) % 7
        if days_ahead == 0 and (hour, minute) <= (now.hour, now.minute):
            days_ahead = 7
        return (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)

    raise ValueError("smart_datetime")
