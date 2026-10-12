from datetime import datetime, time
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
