from __future__ import annotations

from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import cloud, google_auth, storage
from .calendar_sync import create_event, delete_event, get_service
from .dates import REPEATS, format_due, parse_due, parse_repeat
from .google_auth import ALL_SCOPES, NotSignedIn, account_name, get_credentials
from .models import DEFAULT_BUCKET

app = typer.Typer(
    help="A terminal to-do list that can sync tasks to Google Calendar.",
    no_args_is_help=True,
)
console = Console()

def _parse_due(due: Optional[str]) -> Optional[datetime]:
    try:
        return parse_due(due)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def add(
    title: str = typer.Argument(..., help="What needs to be done"),
    due: Optional[str] = typer.Option(
        None, "--due", "-d", help="Due date/time, e.g. '2026-10-15 18:00'"
    ),
    bucket: str = typer.Option(
        DEFAULT_BUCKET, "--bucket", "-b", help="Bucket, e.g. work or personal"
    ),
    note: str = typer.Option("", "--note", "-n", help="Notes for this task"),
    repeat: str = typer.Option(
        "", "--repeat", "-r", help=f"Repeat when completed: {', '.join(REPEATS)} (needs --due)"
    ),
) -> None:
    """Add a new task."""
    try:
        rule = parse_repeat(repeat)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    due_at = _parse_due(due)
    if rule and not due_at:
        raise typer.BadParameter("--repeat needs a --due date to count from.")
    task = storage.add_task(title, due_at, bucket.strip().lower(), note, rule)
    suffix = f" (due {task.due})" if task.due else ""
    if task.repeat:
        suffix += f" ↻ {task.repeat}"
    console.print(
        f"[green]Added[/green] #{task.id} [cyan]\\[{task.bucket}][/cyan]: {task.title}{suffix}"
    )


@app.command("list")
def list_cmd(
    all: bool = typer.Option(False, "--all", "-a", help="Include completed tasks"),
    bucket: Optional[str] = typer.Option(
        None, "--bucket", "-b", help="Only show this bucket"
    ),
) -> None:
    """List tasks (all buckets, or one with --bucket)."""
    tasks = storage.list_tasks(
        include_done=all, bucket=bucket.strip().lower() if bucket else None
    )
    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        raise typer.Exit()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", justify="right")
    table.add_column("Bucket", style="cyan")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Note")
    table.add_column("Due")
    table.add_column("Synced")
    for t in tasks:
        status = "[green]done[/green]" if t.done else "[yellow]pending[/yellow]"
        due = format_due(t.due, short=False) if t.due else "-"
        if t.repeat:
            due += f" ↻{t.repeat}"
        synced = "yes" if t.gcal_event_id else "-"
        table.add_row(str(t.id), t.bucket, status, t.title, "✎" if t.notes else "", due, synced)
    console.print(table)


@app.command()
def note(
    task_id: int,
    text: Optional[str] = typer.Argument(None, help="Text to append as a new line"),
    clear: bool = typer.Option(False, "--clear", help="Delete all notes on the task"),
) -> None:
    """Show a task's notes, or append a line to them."""
    task = storage.get_task(task_id)
    if not task:
        console.print(f"[red]No task with id {task_id}[/red]")
        raise typer.Exit(code=1)
    if clear:
        storage.set_notes(task_id, "")
        console.print(f"[green]Cleared notes[/green] on #{task_id}")
    elif text:
        storage.set_notes(task_id, f"{task.notes}\n{text}" if task.notes else text)
        console.print(f"[green]Added note[/green] to #{task_id} {task.title}")
    else:
        console.print(f"[bold]#{task.id} {task.title}[/bold] [cyan]\\[{task.bucket}][/cyan]")
        console.print(Text(task.notes) if task.notes else "[dim]No notes.[/dim]")


@app.command()
def ui() -> None:
    """Open the interactive terminal UI."""
    from .ui import run

    run()


@app.command()
def tray(
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in the background"),
    install_autostart: bool = typer.Option(
        False, "--install-autostart", help="Start the tray icon automatically at login"
    ),
    remove_autostart: bool = typer.Option(
        False, "--remove-autostart", help="Stop starting the tray icon at login"
    ),
) -> None:
    """Show a panel icon with your pending-task count; click it to list them."""
    from . import tray as tray_mod

    if install_autostart:
        path = tray_mod.install_autostart()
        console.print(f"[green]Will start at login:[/green] {path}")
        return
    if remove_autostart:
        gone = tray_mod.remove_autostart()
        console.print("[green]Autostart removed.[/green]" if gone else "[dim]Autostart wasn't set.[/dim]")
        return
    if detach:
        tray_mod.spawn_detached()
        console.print("[green]Tray icon started.[/green]")
        return
    raise typer.Exit(code=tray_mod.run())


@app.command()
def buckets() -> None:
    """List buckets with their pending task counts."""
    rows = storage.bucket_counts()
    if not rows:
        console.print("[dim]No buckets yet.[/dim]")
        raise typer.Exit()
    for name, pending in rows:
        console.print(f"[cyan]{name}[/cyan]  {pending} pending")


@app.command()
def mv(task_id: int, bucket: str) -> None:
    """Move a task to another bucket."""
    task = storage.get_task(task_id)
    if not task:
        console.print(f"[red]No task with id {task_id}[/red]")
        raise typer.Exit(code=1)
    storage.set_bucket(task_id, bucket.strip().lower())
    console.print(f"[green]Moved[/green] #{task_id} to [cyan]{bucket.strip().lower()}[/cyan]")


@app.command()
def done(task_id: int) -> None:
    """Mark a task as done."""
    task = storage.get_task(task_id)
    if not task:
        console.print(f"[red]No task with id {task_id}[/red]")
        raise typer.Exit(code=1)
    nxt = storage.mark_done(task_id)
    console.print(f"[green]Marked done:[/green] #{task_id} {task.title}")
    if nxt and nxt.due:
        console.print(f"[cyan]Next:[/cyan] #{nxt.id} due {format_due(nxt.due, short=False)} ↻ {nxt.repeat}")


@app.command()
def rm(task_id: int) -> None:
    """Delete a task, removing its Calendar event if it has one."""
    task = storage.get_task(task_id)
    if not task:
        console.print(f"[red]No task with id {task_id}[/red]")
        raise typer.Exit(code=1)
    if task.gcal_event_id:
        try:
            delete_event(get_service(), task.gcal_event_id)
        except Exception as exc:  # noqa: BLE001 - surface any Calendar API error
            console.print(f"[yellow]Warning:[/yellow] could not remove calendar event: {exc}")
    storage.delete_task(task_id)
    console.print(f"[green]Removed:[/green] #{task_id} {task.title}")


def _cloud_sync() -> bool:
    """Merge tasks with the cloud copy. Returns False (after explaining) if it failed."""
    try:
        result = cloud.sync()
    except (cloud.CloudError, NotSignedIn) as exc:
        console.print(f"[yellow]Cloud sync skipped:[/yellow] {exc}")
        return False
    if result.changed:
        console.print(
            f"[cyan]Cloud:[/cyan] pulled {result.pulled}, pushed {result.pushed} task(s)"
        )
    else:
        console.print("[cyan]Cloud:[/cyan] up to date")
    return True


@app.command()
def login() -> None:
    """Sign in with Google so your tasks sync between machines (and to Calendar)."""
    try:
        get_credentials(ALL_SCOPES)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    name = account_name()
    console.print(f"[green]Signed in[/green]{f' as {name}' if name else ''}.")
    _cloud_sync()


@app.command()
def logout() -> None:
    """Sign out of Google on this machine. Your local tasks are kept."""
    if google_auth.logout():
        console.print("[green]Signed out.[/green] Local tasks are untouched.")
    else:
        console.print("[dim]Wasn't signed in.[/dim]")


@app.command()
def sync(
    reminder: int = typer.Option(
        30, "--reminder", "-r", help="Popup reminder, minutes before due"
    ),
) -> None:
    """Sync with Google: merge tasks with your other machines, then update Calendar.

    When signed in (term-todo login), tasks are merged with the copy in your Google
    account. Pending tasks with a due date are pushed to Google Calendar as events,
    and events for tasks you've marked done are removed.
    """
    cloud_on = google_auth.cloud_enabled()
    if cloud_on:
        _cloud_sync()

    service = get_service()

    to_push = storage.tasks_needing_push()
    for task in to_push:
        assert task.due is not None
        event_id = create_event(
            service, f"[{task.bucket}] {task.title}", task.due, reminder_minutes=reminder
        )
        storage.set_gcal_event_id(task.id, event_id)
        console.print(f"[green]Pushed[/green] #{task.id} -> calendar event {event_id}")

    to_clean = storage.tasks_needing_event_removed()
    for task in to_clean:
        assert task.gcal_event_id is not None
        delete_event(service, task.gcal_event_id)
        storage.set_gcal_event_id(task.id, None)
        console.print(f"[green]Cleared calendar event for completed[/green] #{task.id}")

    if not to_push and not to_clean:
        console.print("[dim]Calendar: nothing to sync.[/dim]")
    elif cloud_on:
        _cloud_sync()  # publish the new event ids so other machines don't duplicate them
    if not cloud_on:
        console.print(
            "[dim]Tip: run `term-todo login` to also keep your tasks in sync across machines.[/dim]"
        )


if __name__ == "__main__":
    app()
