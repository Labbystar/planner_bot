from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


WEEKDAY_MAP = {
    "mon": 0, "monday": 0, "пн": 0, "понедельник": 0,
    "tue": 1, "tuesday": 1, "вт": 1, "вторник": 1,
    "wed": 2, "wednesday": 2, "ср": 2, "среда": 2,
    "thu": 3, "thursday": 3, "чт": 3, "четверг": 3,
    "fri": 4, "friday": 4, "пт": 4, "пятница": 4,
    "sat": 5, "saturday": 5, "сб": 5, "суббота": 5,
    "sun": 6, "sunday": 6, "вс": 6, "воскресенье": 6,
}

WEEKDAY_HUMAN_RU = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}


def validate_timezone_name(tz_name: str) -> str:
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Неизвестная таймзона: {tz_name}") from exc
    return tz_name


def current_time_in_timezone(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def parse_datetime_local(date_part: str, time_part: str, tz_name: str) -> datetime:
    naive = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=ZoneInfo(tz_name))


def parse_hhmm(value: str) -> tuple[int, int]:
    dt = datetime.strptime(value, "%H:%M")
    return dt.hour, dt.minute


def parse_weekday(value: str) -> int:
    key = value.strip().lower()
    if key not in WEEKDAY_MAP:
        raise ValueError("Неверный день недели")
    return WEEKDAY_MAP[key]


def fmt_local_time_for_user(dt_utc: datetime, tz_name: str) -> str:
    local_dt = dt_utc.astimezone(ZoneInfo(tz_name))
    return local_dt.strftime("%d.%m.%Y %H:%M")
