import calendar
from datetime import datetime, time, timedelta
from typing import Optional

DATE_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"]


def parse_due(due: Optional[str]) -> Optional[datetime]:
    """Parse a due string; returns None for empty input, raises ValueError if invalid."""
    if not due or not due.strip():
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(due.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse '{due}'. Try 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'.")


def has_time(due: datetime) -> bool:
    """A due of exactly 00:00 means 'date only' (no time was chosen)."""
    return due.time() != time(0, 0)


def format_due(due: datetime, short: bool = True) -> str:
    date_fmt = "%a %d %b" if short else "%Y-%m-%d"
    return due.strftime(f"{date_fmt} %H:%M" if has_time(due) else date_fmt)


def is_overdue(due: datetime, now: datetime) -> bool:
    """Date-only tasks stay on time through the whole day."""
    return due < now if has_time(due) else due.date() < now.date()


REPEATS = ("daily", "weekly", "monthly")


def parse_repeat(value: Optional[str]) -> str:
    """Normalise a repeat rule; '' means no repeat. Raises ValueError if unknown."""
    value = (value or "").strip().lower()
    if value in ("", "none", "no", "never"):
        return ""
    if value not in REPEATS:
        raise ValueError(f"Unknown repeat '{value}'. Use one of: {', '.join(REPEATS)}.")
    return value


def _step(due: datetime, repeat: str) -> datetime:
    if repeat == "daily":
        return due + timedelta(days=1)
    if repeat == "weekly":
        return due + timedelta(weeks=1)
    month = due.month % 12 + 1
    year = due.year + (due.month == 12)
    day = min(due.day, calendar.monthrange(year, month)[1])
    return due.replace(year=year, month=month, day=day)


def next_due(due: datetime, repeat: str, now: datetime) -> datetime:
    """The first occurrence after `due` that falls after today (skips missed ones)."""
    nxt = _step(due, repeat)
    while nxt.date() <= now.date():
        nxt = _step(nxt, repeat)
    return nxt
