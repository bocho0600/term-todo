"""Sync tasks between machines through the user's Google Drive (hidden app data folder).

Each task has a stable ``uid`` and an ``updated_at`` UTC timestamp. Syncing merges the
local and remote copies per task, newest edit wins; deletions travel as tombstones so
they reach every machine.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from . import storage
from .google_auth import CLOUD_SCOPES, get_credentials

FILE_NAME = "term-todo.json"
FORMAT_VERSION = 1
TOMBSTONE_DAYS = 90

_LOCK = threading.Lock()  # one sync at a time (UI timer, manual sync, tray thread)

Row = Dict[str, Any]


class CloudError(Exception):
    """A problem reaching or reading the cloud copy, with a message fit to show the user."""


class RemoteStore(Protocol):
    def read(self) -> Optional[List[Row]]: ...
    def write(self, rows: List[Row]) -> None: ...


@dataclass
class SyncResult:
    pulled: int = 0  # tasks created/changed on this machine from the cloud copy
    pushed: int = 0  # tasks created/changed in the cloud copy from this machine

    @property
    def changed(self) -> bool:
        return bool(self.pulled or self.pushed)


def merge(local: List[Row], remote: List[Row]) -> Tuple[List[Row], List[Row], int]:
    """Merge by uid, newest ``updated_at`` wins (ties keep the local copy).

    Returns (merged rows, rows to write locally, number of rows to write remotely).
    """
    lmap = {r["uid"]: r for r in local}
    rmap = {r["uid"]: r for r in remote}
    merged: List[Row] = []
    to_local: List[Row] = []
    pushed = 0
    for uid in lmap.keys() | rmap.keys():
        lrow, rrow = lmap.get(uid), rmap.get(uid)
        if lrow is None:
            winner = rrow
            to_local.append(rrow)
        elif rrow is None:
            winner = lrow
            pushed += 1
        elif rrow["updated_at"] > lrow["updated_at"]:
            winner = rrow
            if rrow != lrow:
                to_local.append(rrow)
        else:
            winner = lrow
            if rrow != lrow:
                pushed += 1
        merged.append(winner)
    merged.sort(key=lambda r: (r["created_at"], r["uid"]))
    return merged, to_local, pushed


def sync(store: Optional[RemoteStore] = None) -> SyncResult:
    """Pull, merge, and push. Safe to call repeatedly."""
    with _LOCK:
        store = store or DriveStore.connect()
        remote = store.read()
        local = storage.export_all()
        merged, to_local, pushed = merge(local, remote or [])

        cutoff = (datetime.now(timezone.utc) - timedelta(days=TOMBSTONE_DAYS)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        if to_local:
            storage.import_rows(to_local)
        storage.purge_tombstones(cutoff)
        merged = [r for r in merged if not (r["deleted"] and r["updated_at"] < cutoff)]

        if remote is None or pushed or len(merged) != len(remote):
            store.write(merged)
        return SyncResult(pulled=len(to_local), pushed=pushed)


class DriveStore:
    """The cloud copy: one JSON file in Drive's hidden appDataFolder."""

    def __init__(self, service: Any) -> None:
        self.service = service

    @classmethod
    def connect(cls) -> "DriveStore":
        from googleapiclient.discovery import build

        creds = get_credentials(CLOUD_SCOPES, interactive=False)
        return cls(build("drive", "v3", credentials=creds, cache_discovery=False))

    def _call(self, request: Any) -> Any:
        from googleapiclient.errors import HttpError

        try:
            return request.execute()
        except HttpError as exc:
            if exc.resp.status == 403 and "has not been used" in str(exc):
                raise CloudError(
                    "The Google Drive API isn't enabled for your project yet. Enable it at "
                    "https://console.cloud.google.com/apis/library/drive.googleapis.com "
                    "and try again in a minute."
                ) from exc
            raise CloudError(f"Google Drive error: {exc}") from exc

    def _find(self) -> Optional[str]:
        res = self._call(
            self.service.files().list(
                spaces="appDataFolder",
                q=f"name = '{FILE_NAME}' and trashed = false",
                fields="files(id)",
                pageSize=1,
            )
        )
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def read(self) -> Optional[List[Row]]:
        file_id = self._find()
        if file_id is None:
            return None
        raw = self._call(self.service.files().get_media(fileId=file_id))
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if data.get("version", 1) > FORMAT_VERSION:
            raise CloudError("Your cloud data was written by a newer term-todo. Please upgrade.")
        return data["tasks"]

    def write(self, rows: List[Row]) -> None:
        from googleapiclient.http import MediaInMemoryUpload

        body = json.dumps({"version": FORMAT_VERSION, "tasks": rows}).encode("utf-8")
        media = MediaInMemoryUpload(body, mimetype="application/json")
        file_id = self._find()
        if file_id:
            self._call(self.service.files().update(fileId=file_id, media_body=media))
        else:
            self._call(
                self.service.files().create(
                    body={"name": FILE_NAME, "parents": ["appDataFolder"]},
                    media_body=media,
                    fields="id",
                )
            )
