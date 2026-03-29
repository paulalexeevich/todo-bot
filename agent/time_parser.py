"""Parse a short time string into HH:MM (24h). Returns None if unparseable."""
import re


def parse_time(text: str) -> str | None:
    text = text.strip().lower()

    # HH:MM or H:MM
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return f"{h:02d}:{mn:02d}"

    # 9am, 3pm, 9:30am, 3:30pm, 22:27pm (already 24h but user appended pm — trust the digits)
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        suffix = m.group(3)
        # Only apply am/pm conversion if the hour is in 12h range (1-12).
        # If h >= 13 the user wrote 24h time with a trailing "pm" — keep as-is.
        if h <= 12:
            if suffix == "pm" and h != 12:
                h += 12
            if suffix == "am" and h == 12:
                h = 0
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return f"{h:02d}:{mn:02d}"

    # Plain hour: "9", "18"
    m = re.fullmatch(r"(\d{1,2})", text)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    return None
