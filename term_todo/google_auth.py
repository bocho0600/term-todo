"""Google sign-in shared by Calendar sync and cloud task sync."""
from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from .config import CREDENTIALS_PATH, TOKEN_PATH

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
# Hidden per-app storage in the user's Drive. The app can only see its own files there.
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.appdata"

CALENDAR_SCOPES = [CALENDAR_SCOPE]
CLOUD_SCOPES = [DRIVE_SCOPE]
ALL_SCOPES = [CALENDAR_SCOPE, DRIVE_SCOPE]


class NotSignedIn(Exception):
    """Raised when a Google call needs a sign-in that hasn't happened (or has expired)."""


def granted_scopes() -> set:
    """Scopes the cached login was granted (empty if not signed in)."""
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except (OSError, ValueError):
        return set()
    scopes = data.get("scopes") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    return set(scopes)


def has_scopes(required: Iterable[str]) -> bool:
    return set(required) <= granted_scopes()


def cloud_enabled() -> bool:
    """True when this machine is signed in with permission to sync tasks via Drive."""
    return has_scopes(CLOUD_SCOPES)


def get_credentials(required: Iterable[str] = ALL_SCOPES, interactive: bool = True) -> Any:
    """Return valid credentials covering `required`.

    Reuses the cached login when it already grants those scopes. Otherwise runs the
    browser sign-in (asking for *all* scopes, so one login covers everything) — or
    raises NotSignedIn when `interactive` is False.
    """
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    required = list(required)
    creds = None
    if has_scopes(required):
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), sorted(granted_scopes()))
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    TOKEN_PATH.write_text(creds.to_json())
                except RefreshError:
                    creds = None  # revoked or expired (e.g. 7-day Testing-mode limit)
            else:
                creds = None
    if creds is not None:
        return creds

    if not interactive:
        raise NotSignedIn("Not signed in to Google. Run `term-todo login`.")
    return _browser_login()


def _browser_login() -> Any:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Missing Google OAuth client file at {CREDENTIALS_PATH}.\n"
            "See the README ('Google sign-in setup') for how to create it."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), ALL_SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    TOKEN_PATH.chmod(0o600)
    return creds


def account_name() -> Optional[str]:
    """Best-effort label for the signed-in account (the primary calendar's title)."""
    try:
        from googleapiclient.discovery import build

        creds = get_credentials(CALENDAR_SCOPES, interactive=False)
        cal = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return cal.events().list(calendarId="primary", maxResults=1).execute().get("summary")
    except Exception:  # noqa: BLE001 - purely cosmetic
        return None


def logout() -> bool:
    """Forget the cached login. Local tasks are untouched."""
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        return True
    return False
