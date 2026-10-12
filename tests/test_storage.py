import sqlite3
from datetime import datetime

from term_todo import storage


def test_add_and_get():
    t = storage.add_task("Write tests", datetime(2026, 10, 15, 9, 0), "work", "some notes")
    got = storage.get_task(t.id)
    assert got is not None
    assert (got.title, got.bucket, got.notes, got.done) == ("Write tests", "work", "some notes", False)
    assert got.due == datetime(2026, 10, 15, 9, 0)


def test_defaults():
    t = storage.add_task("Plain", None)
    assert t.bucket == "inbox"
    assert t.notes == ""
    assert t.due is None


def test_get_missing_returns_none():
    assert storage.get_task(999) is None


def test_list_filters_by_bucket_and_done():
    a = storage.add_task("a", None, "x")
    storage.add_task("b", None, "y")
    storage.mark_done(a.id)
    assert [t.title for t in storage.list_tasks()] == ["b"]
    assert {t.title for t in storage.list_tasks(include_done=True)} == {"a", "b"}
    assert [t.title for t in storage.list_tasks(bucket="y")] == ["b"]
    assert storage.list_tasks(bucket="x") == []


def test_list_sorted_by_bucket_then_due_with_undated_last():
    storage.add_task("late", datetime(2026, 12, 1), "a")
    storage.add_task("undated", None, "a")
    storage.add_task("early", datetime(2026, 11, 1), "a")
    storage.add_task("other", None, "0")
    assert [t.title for t in storage.list_tasks()] == ["other", "early", "late", "undated"]


def test_set_done_toggles():
    t = storage.add_task("t", None)
    storage.set_done(t.id, True)
    assert storage.get_task(t.id).done
    storage.set_done(t.id, False)
    assert not storage.get_task(t.id).done


def test_update_task_and_notes_and_bucket():
    t = storage.add_task("old", None, "a")
    storage.update_task(t.id, "new", datetime(2026, 1, 2), "b", "n")
    got = storage.get_task(t.id)
    assert (got.title, got.due, got.bucket, got.notes) == ("new", datetime(2026, 1, 2), "b", "n")
    storage.set_notes(t.id, "changed")
    storage.set_bucket(t.id, "c")
    got = storage.get_task(t.id)
    assert (got.notes, got.bucket) == ("changed", "c")


def test_delete():
    t = storage.add_task("t", None)
    storage.delete_task(t.id)
    assert storage.get_task(t.id) is None


def test_bucket_counts_only_count_pending():
    storage.add_task("1", None, "a")
    done = storage.add_task("2", None, "a")
    storage.add_task("3", None, "b")
    storage.mark_done(done.id)
    assert storage.bucket_counts() == [("a", 1), ("b", 1)]


def test_bucket_with_only_done_tasks_has_zero_pending():
    t = storage.add_task("x", None, "a")
    storage.mark_done(t.id)
    assert storage.bucket_counts() == [("a", 0)]


def test_sync_queries():
    due = datetime(2026, 10, 15)
    pending = storage.add_task("pending", due)
    undated = storage.add_task("undated", None)
    synced = storage.add_task("synced", due)
    storage.set_gcal_event_id(synced.id, "evt1")
    finished = storage.add_task("finished", due)
    storage.set_gcal_event_id(finished.id, "evt2")
    storage.mark_done(finished.id)

    assert [t.id for t in storage.tasks_needing_push()] == [pending.id]
    assert [t.id for t in storage.tasks_needing_event_removed()] == [finished.id]
    assert undated.id not in {t.id for t in storage.tasks_needing_push()}


def test_old_database_is_migrated(fresh_db):
    """A DB created before buckets/notes existed gains those columns, keeping its data."""
    conn = sqlite3.connect(fresh_db)
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,"
        " due TEXT, done INTEGER NOT NULL DEFAULT 0, gcal_event_id TEXT, created_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO tasks (title, created_at) VALUES ('legacy', '2026-01-01T00:00:00')")
    conn.commit()
    conn.close()

    (task,) = storage.list_tasks()
    assert (task.title, task.bucket, task.notes) == ("legacy", "inbox", "")
    # opening it twice must not try to add the columns again
    assert len(storage.list_tasks()) == 1


def test_delete_leaves_a_tombstone_for_syncing():
    t = storage.add_task("t", None)
    storage.delete_task(t.id)
    (row,) = storage.export_all()
    assert row["deleted"] == 1 and row["uid"]


def test_every_edit_bumps_updated_at():
    t = storage.add_task("t", None)
    before = storage.export_all()[0]["updated_at"]
    storage.set_notes(t.id, "n")
    assert storage.export_all()[0]["updated_at"] > before


def test_migration_gives_legacy_rows_unique_uids(fresh_db):
    conn = sqlite3.connect(fresh_db)
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,"
        " due TEXT, done INTEGER NOT NULL DEFAULT 0, gcal_event_id TEXT, created_at TEXT NOT NULL)"
    )
    for name in ("one", "two"):
        conn.execute("INSERT INTO tasks (title, created_at) VALUES (?, '2026-01-01T00:00:00')", (name,))
    conn.commit()
    conn.close()
    rows = storage.export_all()
    assert len({r["uid"] for r in rows}) == 2 and all(r["updated_at"] for r in rows)


def test_import_rows_upserts_by_uid():
    t = storage.add_task("local", None)
    (row,) = storage.export_all()
    storage.import_rows([{**row, "title": "from cloud"}])
    assert storage.get_task(t.id).title == "from cloud"
    assert len(storage.export_all()) == 1
