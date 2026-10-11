import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, List, Optional

from .config import DB_PATH
from .models import Task

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


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
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
    )


def add_task(title: str, due: Optional[datetime]) -> Task:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, due, done, created_at) VALUES (?, ?, 0, ?)",
            (title, due.isoformat() if due else None, datetime.now().isoformat()),
        )
        task_id = cur.lastrowid
    task = get_task(task_id)
    assert task is not None
    return task


def get_task(task_id: int) -> Optional[Task]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None


def list_tasks(include_done: bool = False) -> List[Task]:
    query = "SELECT * FROM tasks"
    if not include_done:
        query += " WHERE done = 0"
    query += " ORDER BY (due IS NULL), due, id"
    with connect() as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_task(r) for r in rows]


def mark_done(task_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))


def delete_task(task_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def set_gcal_event_id(task_id: int, event_id: Optional[str]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET gcal_event_id = ? WHERE id = ?", (event_id, task_id)
        )


def tasks_needing_push() -> List[Task]:
    """Pending tasks with a due date that have never been pushed to Calendar."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE done = 0 AND due IS NOT NULL AND gcal_event_id IS NULL"
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def tasks_needing_event_removed() -> List[Task]:
    """Completed tasks that still have a linked Calendar event to clean up."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE done = 1 AND gcal_event_id IS NOT NULL"
        ).fetchall()
    return [_row_to_task(r) for r in rows]
