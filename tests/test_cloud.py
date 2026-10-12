import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from term_todo import cloud, storage
from term_todo.cloud import CloudError, DriveStore, merge


def row(uid, title="t", updated="2026-01-01T00:00:00.000000Z", deleted=0, **kw):
    base = dict(uid=uid, title=title, due=None, done=0, gcal_event_id=None,
                created_at="2026-01-01T00:00:00", bucket="inbox", notes="",
                updated_at=updated, deleted=deleted)
    base.update(kw)
    return base


# ---------- merge rules ----------

def test_merge_unions_disjoint_tasks():
    merged, to_local, pushed = merge([row("a")], [row("b")])
    assert {r["uid"] for r in merged} == {"a", "b"}
    assert [r["uid"] for r in to_local] == ["b"]
    assert pushed == 1


def test_merge_newest_edit_wins_both_ways():
    old, new = "2026-01-01T00:00:00.000000Z", "2026-02-01T00:00:00.000000Z"
    merged, to_local, pushed = merge([row("a", "local-new", new)], [row("a", "remote-old", old)])
    assert merged[0]["title"] == "local-new" and to_local == [] and pushed == 1
    merged, to_local, pushed = merge([row("a", "local-old", old)], [row("a", "remote-new", new)])
    assert merged[0]["title"] == "remote-new" and len(to_local) == 1 and pushed == 0


def test_merge_identical_is_a_no_op():
    r = row("a")
    merged, to_local, pushed = merge([r], [dict(r)])
    assert to_local == [] and pushed == 0 and merged == [r]


def test_merge_newer_deletion_beats_older_edit():
    merged, to_local, _ = merge(
        [row("a", "edited", "2026-01-01T00:00:00.000000Z")],
        [row("a", "edited", "2026-03-01T00:00:00.000000Z", deleted=1)],
    )
    assert merged[0]["deleted"] == 1 and to_local[0]["deleted"] == 1


# ---------- two machines, one cloud copy ----------

class FakeStore:
    def __init__(self):
        self.rows = None
        self.writes = 0

    def read(self):
        return None if self.rows is None else json.loads(json.dumps(self.rows))

    def write(self, rows):
        self.rows = json.loads(json.dumps(rows))
        self.writes += 1


@pytest.fixture
def machines(tmp_path, monkeypatch):
    @contextmanager
    def on(name):
        monkeypatch.setattr(storage, "DB_PATH", tmp_path / f"{name}.db")
        yield

    return on


def titles(include_done=True):
    return sorted(t.title for t in storage.list_tasks(include_done=include_done))


def test_first_sync_uploads_and_second_machine_downloads(machines):
    store = FakeStore()
    with machines("laptop"):
        storage.add_task("buy milk", None, "home", "2%")
        result = cloud.sync(store)
        assert (result.pulled, result.pushed) == (0, 1)
    with machines("desktop"):
        result = cloud.sync(store)
        assert result.pulled == 1
        (t,) = storage.list_tasks()
        assert (t.title, t.bucket, t.notes) == ("buy milk", "home", "2%")


def test_edits_done_and_deletes_propagate(machines):
    store = FakeStore()
    with machines("a"):
        keep = storage.add_task("keep", None)
        gone = storage.add_task("gone", None)
        finish = storage.add_task("finish", None)
        cloud.sync(store)
    with machines("b"):
        cloud.sync(store)
        by_title = {t.title: t for t in storage.list_tasks()}
        storage.update_task(by_title["keep"].id, "keep (edited)", None, "work", "n")
        storage.delete_task(by_title["gone"].id)
        storage.set_done(by_title["finish"].id, True)
        cloud.sync(store)
    with machines("a"):
        cloud.sync(store)
        assert titles() == ["finish", "keep (edited)"]
        assert storage.get_task(gone.id) is None
        assert storage.get_task(finish.id).done
        assert storage.get_task(keep.id).bucket == "work"


def test_each_machines_new_tasks_are_merged_not_lost(machines):
    store = FakeStore()
    with machines("a"):
        storage.add_task("from a", None)
        cloud.sync(store)
    with machines("b"):
        storage.add_task("from b", None)
        cloud.sync(store)
        assert titles() == ["from a", "from b"]
    with machines("a"):
        cloud.sync(store)
        assert titles() == ["from a", "from b"]


def test_concurrent_edit_newest_wins(machines):
    store = FakeStore()
    with machines("a"):
        t = storage.add_task("task", None)
        cloud.sync(store)
    with machines("b"):
        cloud.sync(store)
        tb = storage.list_tasks()[0]
        storage.update_task(tb.id, "edited on b", None, "inbox", "")
        cloud.sync(store)
    with machines("a"):
        storage.update_task(t.id, "edited on a (later)", None, "inbox", "")
        cloud.sync(store)
    with machines("b"):
        cloud.sync(store)
        assert titles() == ["edited on a (later)"]


def test_calendar_link_is_shared_so_other_machines_dont_duplicate_events(machines):
    store = FakeStore()
    with machines("a"):
        t = storage.add_task("meeting", datetime(2026, 10, 20, 9, 0))
        storage.set_gcal_event_id(t.id, "evt123")
        cloud.sync(store)
    with machines("b"):
        cloud.sync(store)
        assert storage.tasks_needing_push() == []
        assert storage.list_tasks()[0].gcal_event_id == "evt123"


def test_sync_is_idempotent_and_skips_needless_uploads(machines):
    store = FakeStore()
    with machines("a"):
        storage.add_task("x", None)
        cloud.sync(store)
        writes = store.writes
        result = cloud.sync(store)
        assert not result.changed and store.writes == writes


def test_old_tombstones_are_purged(machines):
    store = FakeStore()
    ancient = (datetime.now(timezone.utc) - timedelta(days=cloud.TOMBSTONE_DAYS + 5)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    store.rows = [row("dead", deleted=1, updated=ancient)]
    with machines("a"):
        cloud.sync(store)
        assert storage.export_all() == []
        assert store.rows == []


# ---------- DriveStore against a stub Drive service ----------

class _Req:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class StubDrive:
    """Just enough of googleapiclient's Drive v3 `files()` surface."""

    def __init__(self):
        self.content = None
        self.created = []

    def files(self):
        return self

    def list(self, **kw):
        assert kw["spaces"] == "appDataFolder"
        return _Req(lambda: {"files": [{"id": "F1"}] if self.content is not None else []})

    def get_media(self, fileId):
        return _Req(lambda: self.content)

    def create(self, body, media_body, fields):
        assert body["parents"] == ["appDataFolder"]
        self.created.append(body["name"])
        return _Req(lambda: self._store(media_body))

    def update(self, fileId, media_body):
        return _Req(lambda: self._store(media_body))

    def _store(self, media):
        self.content = media.getbytes(0, media.size())
        return {"id": "F1"}


def test_drive_store_round_trip():
    svc = StubDrive()
    store = DriveStore(svc)
    assert store.read() is None
    store.write([row("a", "hello")])
    assert svc.created == [cloud.FILE_NAME]
    assert store.read()[0]["title"] == "hello"
    store.write([row("a", "again")])
    assert svc.created == [cloud.FILE_NAME]  # updated in place, not re-created
    assert store.read()[0]["title"] == "again"


def test_drive_store_rejects_newer_format():
    svc = StubDrive()
    svc.content = json.dumps({"version": 99, "tasks": []}).encode()
    with pytest.raises(CloudError):
        DriveStore(svc).read()
