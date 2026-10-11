from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Any

from .config import CREDENTIALS_PATH, TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _local_tz() -> tzinfo:
    tz = datetime.now().astimezone().tzinfo
    assert tz is not None
    return tz


def _to_aware(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=_local_tz())


def _load_credentials() -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing Google OAuth client file at {CREDENTIALS_PATH}.\n"
                    "See README.md 'Google Calendar setup' for how to create it."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def get_service() -> Any:
    from googleapiclient.discovery import build

    creds = _load_credentials()
    return build("calendar", "v3", credentials=creds)


def create_event(
    service: Any, title: str, due: datetime, reminder_minutes: int = 30
) -> str:
    start = _to_aware(due)
    end = start + timedelta(minutes=30)
    body = {
        "summary": title,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        },
    }
    event = service.events().insert(calendarId="primary", body=body).execute()
    return event["id"]


def delete_event(service: Any, event_id: str) -> None:
    from googleapiclient.errors import HttpError

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as exc:
        if exc.resp.status != 404:
            raise
