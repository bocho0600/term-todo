from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Any

from .dates import has_time
from .google_auth import CALENDAR_SCOPES, get_credentials


def _local_tz() -> tzinfo:
    tz = datetime.now().astimezone().tzinfo
    assert tz is not None
    return tz


def _to_aware(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=_local_tz())


def get_service() -> Any:
    from googleapiclient.discovery import build

    creds = get_credentials(CALENDAR_SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def build_event_body(title: str, due: datetime, reminder_minutes: int = 30) -> dict:
    """Timed event if the task has a time; otherwise an all-day event."""
    if not has_time(due):
        day = due.date()
        return {
            "summary": title,
            "start": {"date": day.isoformat()},
            "end": {"date": (day + timedelta(days=1)).isoformat()},
            "reminders": {"useDefault": True},
        }
    start = _to_aware(due)
    return {
        "summary": title,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(minutes=30)).isoformat()},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        },
    }


def create_event(
    service: Any, title: str, due: datetime, reminder_minutes: int = 30
) -> str:
    body = build_event_body(title, due, reminder_minutes)
    event = service.events().insert(calendarId="primary", body=body).execute()
    return event["id"]


def delete_event(service: Any, event_id: str) -> None:
    from googleapiclient.errors import HttpError

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as exc:
        if exc.resp.status != 404:
            raise
