import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from .config import DB_PATH
from .dates import next_due
from .models import DEFAULT_BUCKET, Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    gcal_event_id TEXT,
    created_at TEXT NOT NULL
);
"""


def now_utc() -> str:
    """Sortable UTC timestamp; the last-writer-wins clock used when syncing machines."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)")]
        if "notes" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        if "bucket" not in cols:
            conn.execute(
                f"ALTER TABLE tasks ADD COLUMN bucket TEXT NOT NULL DEFAULT '{DEFAULT_BUCKET}'"
            )
        if "repeat" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN repeat TEXT NOT NULL DEFAULT ''")
        if "uid" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN uid TEXT")
        if "updated_at" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
        if "deleted" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")
        for row in conn.execute("SELECT id FROM tasks WHERE uid IS NULL").fetchall():
            conn.execute("UPDATE tasks SET uid = ? WHERE id = ?", (uuid.uuid4().hex, row["id"]))
        conn.execute("UPDATE tasks SET updated_at = ? WHERE updated_at IS NULL", (now_utc(),))
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_uid ON tasks (uid)")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        due=datetime.fromisoformat(row["due"]) if row["due"] else None,
        done=bool(row["done"]),
        gcal_event_id=row["gcal_event_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        bucket=row["bucket"],
        notes=row["notes"],
        repeat=row["repeat"],
        uid=row["uid"],
    )


def add_task(
    title: str,
    due: Optional[datetime],
    bucket: str = DEFAULT_BUCKET,
    notes: str = "",
    repeat: str = "",
) -> Task:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, due, done, created_at, bucket, notes, repeat, uid, updated_at)"
            " VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)",
            (
                title,
                due.isoformat() if due else None,
                datetime.now().isoformat(),
                bucket,
                notes,
                repeat if due else "",
                uuid.uuid4().hex,
                now_utc(),
            ),
        )
        task_id = cur.lastrowid
    task = get_task(task_id)
    assert task is not None
    return task


def get_task(task_id: int) -> Optional[Task]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND deleted = 0", (task_id,)
        ).fetchone()
        return _row_to_task(row) if row else None


def list_tasks(include_done: bool = False, bucket: Optional[str] = None) -> List[Task]:
    clauses, params = ["deleted = 0"], []
    if not include_done:
        clauses.append("done = 0")
    if bucket:
        clauses.append("bucket = ?")
        params.append(bucket)
    query = "SELECT * FROM tasks WHERE " + " AND ".join(clauses)
    query += " ORDER BY bucket, (due IS NULL), due, id"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_task(r) for r in rows]


def mark_done(task_id: int) -> Optional[Task]:
    return set_done(task_id, True)


def set_bucket(task_id: int, bucket: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET bucket = ?, updated_at = ? WHERE id = ?", (bucket, now_utc(), task_id)
        )


def bucket_counts() -> List[tuple]:
    """(bucket, pending_count) for every bucket that has any tasks."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT bucket, SUM(done = 0) AS pending FROM tasks WHERE deleted = 0"
            " GROUP BY bucket ORDER BY bucket"
        ).fetchall()
    return [(r["bucket"], r["pending"] or 0) for r in rows]


def set_done(task_id: int, done: bool) -> Optional[Task]:
    """Set the done flag. Completing a repeating task returns its newly created next copy."""
    task = get_task(task_id)
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET done = ?, updated_at = ? WHERE id = ?", (int(done), now_utc(), task_id)
        )
    if done and task and not task.done and task.repeat and task.due:
        return _spawn_next(task)
    return None


def _spawn_next(task: Task) -> Optional[Task]:
    assert task.due is not None
    due = next_due(task.due, task.repeat, datetime.now())
    with connect() as conn:
        twin = conn.execute(
            "SELECT 1 FROM tasks WHERE deleted = 0 AND done = 0 AND title = ? AND bucket = ?"
            " AND repeat = ? AND due = ?",
            (task.title, task.bucket, task.repeat, due.isoformat()),
        ).fetchone()
    if twin:  # e.g. the task was un-ticked and ticked again
        return None
    return add_task(task.title, due, task.bucket, task.notes, task.repeat)


def update_task(
    task_id: int,
    title: str,
    due: Optional[datetime],
    bucket: str,
    notes: str = "",
    repeat: str = "",
) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET title = ?, due = ?, bucket = ?, notes = ?, repeat = ?,"
            " updated_at = ? WHERE id = ?",
            (
                title,
                due.isoformat() if due else None,
                bucket,
                notes,
                repeat if due else "",
                now_utc(),
                task_id,
            ),
        )


def set_notes(task_id: int, notes: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET notes = ?, updated_at = ? WHERE id = ?", (notes, now_utc(), task_id)
        )


def delete_task(task_id: int) -> None:
    """Soft delete: keep a tombstone so the deletion can propagate to other machines."""
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET deleted = 1, updated_at = ? WHERE id = ?", (now_utc(), task_id)
        )


def set_gcal_event_id(task_id: int, event_id: Optional[str]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET gcal_event_id = ?, updated_at = ? WHERE id = ?",
            (event_id, now_utc(), task_id)
        )


def tasks_needing_push() -> List[Task]:
    """Pending tasks with a due date that have never been pushed to Calendar."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE deleted = 0 AND done = 0"
            " AND due IS NOT NULL AND gcal_event_id IS NULL"
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def tasks_needing_event_removed() -> List[Task]:
    """Completed tasks that still have a linked Calendar event to clean up."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE deleted = 0 AND done = 1 AND gcal_event_id IS NOT NULL"
        ).fetchall()
    return [_row_to_task(r) for r in rows]


# ---- helpers for syncing between machines (see cloud.py) ----

SYNC_FIELDS = (
    "uid", "title", "due", "done", "gcal_event_id", "created_at",
    "bucket", "notes", "repeat", "updated_at", "deleted",
)
_SYNC_DEFAULTS = {"repeat": ""}  # fields older machines don't send yet


def export_all() -> List[Dict[str, Any]]:
    """Every task including deletion tombstones, as plain dicts."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    return [{k: r[k] for k in SYNC_FIELDS} for r in rows]


def import_rows(rows: List[Dict[str, Any]]) -> None:
    """Insert or overwrite tasks by uid, keeping each row's own updated_at."""
    cols = ", ".join(SYNC_FIELDS)
    marks = ", ".join("?" for _ in SYNC_FIELDS)
    updates = ", ".join(f"{c} = excluded.{c}" for c in SYNC_FIELDS if c != "uid")
    with connect() as conn:
        for row in rows:
            conn.execute(
                f"INSERT INTO tasks ({cols}) VALUES ({marks})"
                f" ON CONFLICT(uid) DO UPDATE SET {updates}",
                tuple(row.get(c, _SYNC_DEFAULTS.get(c)) for c in SYNC_FIELDS),
            )


def purge_tombstones(older_than: str) -> None:
    """Permanently drop deletion records last touched before `older_than` (a now_utc() string)."""
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE deleted = 1 AND updated_at < ?", (older_than,))
