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
