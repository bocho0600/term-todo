from typer.testing import CliRunner

from term_todo import storage
from term_todo.cli import app

runner = CliRunner()


def run(*args):
    result = runner.invoke(app, list(args))
    return result


def test_add_and_list():
    r = run("add", "Fix bug", "-b", "Work", "-d", "2026-10-15 18:00", "-n", "check logs")
    assert r.exit_code == 0
    assert "Added #1" in r.output and "work" in r.output
    out = run("list").output
    assert "Fix bug" in out and "work" in out and "2026-10-15 18:00" in out


def test_add_without_options_goes_to_inbox():
    run("add", "Loose end")
    assert storage.get_task(1).bucket == "inbox"


def test_add_rejects_bad_date():
    r = run("add", "x", "-d", "not a date")
    assert r.exit_code != 0
    assert storage.list_tasks() == []


def test_list_empty():
    assert "No tasks found" in run("list").output


def test_list_by_bucket_and_all():
    run("add", "alpha", "-b", "x")
    run("add", "bravo", "-b", "y")
    run("done", "1")
    assert "No tasks found" in run("list", "-b", "x").output  # alpha is done
    assert "alpha" in run("list", "--all", "-b", "x").output
    only_y = run("list", "-b", "y").output
    assert "bravo" in only_y and "alpha" not in only_y


def test_buckets_command():
    assert "No buckets yet" in run("buckets").output
    run("add", "a", "-b", "x")
    run("add", "b", "-b", "x")
    assert "x" in run("buckets").output and "2 pending" in run("buckets").output


def test_mv():
    run("add", "a", "-b", "x")
    assert run("mv", "1", "Y").exit_code == 0
    assert storage.get_task(1).bucket == "y"
    assert run("mv", "99", "z").exit_code == 1


def test_notes_flow():
    run("add", "a")
    assert "No notes" in run("note", "1").output
    run("note", "1", "first")
    run("note", "1", "second")
    assert storage.get_task(1).notes == "first\nsecond"
    assert "first" in run("note", "1").output
    run("note", "1", "--clear")
    assert storage.get_task(1).notes == ""
    assert run("note", "99").exit_code == 1


def test_done_and_missing():
    run("add", "a")
    assert run("done", "1").exit_code == 0
    assert storage.get_task(1).done
    assert run("done", "42").exit_code == 1


def test_rm_without_calendar_event():
    run("add", "a")
    assert run("rm", "1").exit_code == 0
    assert storage.get_task(1) is None
    assert run("rm", "1").exit_code == 1


# ---------- Google sign-in / cloud sync commands (all Google calls faked) ----------

def _fake_google(monkeypatch, signed_in=True):
    from datetime import datetime

    from term_todo import cli, cloud, google_auth

    events = []
    monkeypatch.setattr(google_auth, "cloud_enabled", lambda: signed_in)
    monkeypatch.setattr(cli, "get_service", lambda: object())

    def fake_create(service, title, due, reminder_minutes=30):
        events.append(title)
        return "evt-1"

    monkeypatch.setattr(cli, "create_event", fake_create)
    monkeypatch.setattr(cli, "delete_event", lambda *a, **k: None)
    syncs = []
    monkeypatch.setattr(cloud, "sync", lambda store=None: syncs.append(1) or cloud.SyncResult())
    return events, syncs, datetime


def test_login_signs_in_then_syncs(monkeypatch):
    from term_todo import cli, cloud

    monkeypatch.setattr(cli, "get_credentials", lambda scopes: object())
    monkeypatch.setattr(cli, "account_name", lambda: "me@example.com")
    synced = []
    monkeypatch.setattr(cloud, "sync", lambda store=None: synced.append(1) or cloud.SyncResult())
    r = run("login")
    assert r.exit_code == 0 and "me@example.com" in r.output and synced


def test_login_without_client_file_explains(monkeypatch):
    from term_todo import cli

    def boom(scopes):
        raise FileNotFoundError("Missing Google OAuth client file")

    monkeypatch.setattr(cli, "get_credentials", boom)
    r = run("login")
    assert r.exit_code == 1 and "Missing Google OAuth client file" in r.output


def test_logout(monkeypatch):
    from term_todo import google_auth

    monkeypatch.setattr(google_auth, "logout", lambda: True)
    assert "Signed out" in run("logout").output
    monkeypatch.setattr(google_auth, "logout", lambda: False)
    assert "Wasn't signed in" in run("logout").output


def test_sync_merges_cloud_before_and_after_calendar_changes(monkeypatch):
    events, syncs, datetime = _fake_google(monkeypatch)
    storage.add_task("dated", datetime(2026, 10, 20), "work")
    r = run("sync")
    assert r.exit_code == 0
    assert events == ["[work] dated"]
    assert len(syncs) == 2  # once up front, once to publish the new calendar event id


def test_sync_without_calendar_changes_syncs_cloud_once(monkeypatch):
    events, syncs, _ = _fake_google(monkeypatch)
    storage.add_task("undated", None)
    run("sync")
    assert events == [] and len(syncs) == 1


def test_sync_signed_out_skips_cloud_and_hints(monkeypatch):
    events, syncs, datetime = _fake_google(monkeypatch, signed_in=False)
    storage.add_task("dated", datetime(2026, 10, 20))
    r = run("sync")
    assert syncs == [] and events and "term-todo login" in r.output


def test_add_repeat_needs_due_and_valid_rule():
    assert runner.invoke(app, ["add", "x", "--repeat", "weekly"]).exit_code != 0
    assert runner.invoke(app, ["add", "x", "-d", "2026-10-15", "-r", "sometimes"]).exit_code != 0


def test_done_on_repeating_task_reports_next():
    from datetime import datetime, timedelta

    due = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert runner.invoke(app, ["add", "water plants", "-d", due, "-r", "weekly"]).exit_code == 0
    result = runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0 and "Next:" in result.output
