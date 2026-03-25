
import re
from datetime import datetime

def parse_time_input(text: str):
    text = text.strip()
    patterns = [
        r"(\d{1,2})[:\-\.\s](\d{2})"
    ]
    for p in patterns:
        m = re.match(p, text)
        if m:
            h = int(m.group(1))
            mnt = int(m.group(2))
            if 0 <= h <= 23 and 0 <= mnt <= 59:
                return h, mnt
    return None

def parse_date_input(text: str):
    text = text.strip()
    patterns = [
        r"(\d{1,2})[\.\-\s](\d{1,2})[\.\-\s](\d{2,4})"
    ]
    for p in patterns:
        m = re.match(p, text)
        if m:
            d = int(m.group(1))
            mo = int(m.group(2))
            y = int(m.group(3))
            if y < 100:
                y += 2000
            try:
                return datetime(y, mo, d)
            except:
                return None
    return None
