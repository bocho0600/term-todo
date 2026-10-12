"""The UI's multi-machine sync behaviour, with the cloud and sign-in faked out."""
import asyncio

import pytest
from textual.widgets import DataTable

from term_todo import cloud, google_auth, storage
from term_todo.cloud import SyncResult
from term_todo.ui import TodoApp


@pytest.fixture
def signed_in(monkeypatch):
    monkeypatch.setattr(google_auth, "cloud_enabled", lambda: True)
    monkeypatch.setattr(TodoApp, "SYNC_DELAY", 0.05)
    calls = []

    def fake_sync(store=None):
        calls.append(1)
        return SyncResult()

    monkeypatch.setattr(cloud, "sync", fake_sync)
    return calls


def run(coro_fn):
    asyncio.run(coro_fn())


def test_syncs_when_the_app_opens(signed_in):
    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.3)
            assert len(signed_in) == 1
            assert "synced" in app.sub_title

    run(scenario)


def test_local_change_triggers_a_sync_shortly_after(signed_in):
    storage.add_task("t", None)

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.3)
            before = len(signed_in)
            await pilot.press("space")
            await pilot.pause(0.5)
            assert len(signed_in) == before + 1

    run(scenario)


def test_pulled_tasks_appear_without_restarting(signed_in, monkeypatch):
    def pulling_sync(store=None):
        storage.add_task("from another machine", None)
        return SyncResult(pulled=1)

    monkeypatch.setattr(cloud, "sync", pulling_sync)

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.5)
            assert app.query_one("#tasks", DataTable).row_count == 1

    run(scenario)


def test_offline_keeps_working_and_says_so(signed_in, monkeypatch):
    def broken(store=None):
        raise cloud.CloudError("no network")

    monkeypatch.setattr(cloud, "sync", broken)
    storage.add_task("t", None)

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.3)
            assert "offline" in app.sub_title
            await pilot.press("space")  # still usable
            await pilot.pause(0.3)

    run(scenario)
    assert storage.get_task(1).done


def test_quitting_with_unsynced_changes_syncs_first(signed_in, monkeypatch):
    monkeypatch.setattr(TodoApp, "SYNC_DELAY", 60)  # so only the quit-time sync can run

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.3)
            before = len(signed_in)
            await pilot.press("a")
            await pilot.pause()
            await pilot.press(*"x")
            await pilot.press("ctrl+s")
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause(0.3)
            assert len(signed_in) == before + 1

    run(scenario)


def test_nothing_syncs_when_signed_out(monkeypatch):
    monkeypatch.setattr(google_auth, "cloud_enabled", lambda: False)
    monkeypatch.setattr(cloud, "sync", lambda store=None: pytest.fail("should not sync"))

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("a")
            await pilot.pause()
            await pilot.press(*"x")
            await pilot.press("ctrl+s")
            await pilot.pause(0.3)
            await pilot.press("q")
            await pilot.pause(0.2)

    run(scenario)
