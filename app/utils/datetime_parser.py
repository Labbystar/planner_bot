from __future__ import annotations

import re
from datetime import datetime


def parse_time_input(text: str) -> tuple[int, int] | None:
    value = text.strip()
    m = re.fullmatch(r"(\d{1,2})[:\-\.\s](\d{2})", value)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def parse_date_input(text: str) -> datetime | None:
    value = text.strip()
    m = re.fullmatch(r"(\d{1,2})[\.\-\s](\d{1,2})[\.\-\s](\d{2,4})", value)
    if not m:
        return None

    day = int(m.group(1))
    month = int(m.group(2))
    year = int(m.group(3))
    if year < 100:
        year += 2000

    try:
        return datetime(year, month, day)
    except ValueError:
        return None
