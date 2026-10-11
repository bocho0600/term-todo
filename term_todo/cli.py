from __future__ import annotations

from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import storage
from .calendar_sync import create_event, delete_event, get_service

app = typer.Typer(
    help="A terminal to-do list that can sync tasks to Google Calendar.",
    no_args_is_help=True,
)
console = Console()

DATE_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"]


def _parse_due(due: Optional[str]) -> Optional[datetime]:
    if not due:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(due, fmt)
        except ValueError:
            continue
    raise typer.BadParameter(
        f"Could not parse '{due}'. Try 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'."
    )


@app.command()
def add(
    title: str = typer.Argument(..., help="What needs to be done"),
    due: Optional[str] = typer.Option(
        None, "--due", "-d", help="Due date/time, e.g. '2026-10-15 18:00'"
    ),
) -> None:
    """Add a new task."""
    task = storage.add_task(title, _parse_due(due))
    suffix = f" (due {task.due})" if task.due else ""
    console.print(f"[green]Added[/green] #{task.id}: {task.title}{suffix}")


@app.command("list")
def list_cmd(
    all: bool = typer.Option(False, "--all", "-a", help="Include completed tasks"),
) -> None:
    """List tasks."""
    tasks = storage.list_tasks(include_done=all)
    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        raise typer.Exit()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", justify="right")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Due")
    table.add_column("Synced")
    for t in tasks:
        status = "[green]done[/green]" if t.done else "[yellow]pending[/yellow]"
        due = t.due.strftime("%Y-%m-%d %H:%M") if t.due else "-"
        synced = "yes" if t.gcal_event_id else "-"
        table.add_row(str(t.id), status, t.title, due, synced)
    console.print(table)


@app.command()
def done(task_id: int) -> None:
    """Mark a task as done."""
    task = storage.get_task(task_id)
    if not task:
        console.print(f"[red]No task with id {task_id}[/red]")
        raise typer.Exit(code=1)
    storage.mark_done(task_id)
    console.print(f"[green]Marked done:[/green] #{task_id} {task.title}")


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


@app.command()
def sync(
    reminder: int = typer.Option(
        30, "--reminder", "-r", help="Popup reminder, minutes before due"
    ),
) -> None:
    """Sync tasks with Google Calendar.

    Pushes pending tasks that have a due date as Calendar events, and removes
    the Calendar event for tasks you've since marked done.
    """
    service = get_service()

    to_push = storage.tasks_needing_push()
    for task in to_push:
        assert task.due is not None
        event_id = create_event(service, task.title, task.due, reminder_minutes=reminder)
        storage.set_gcal_event_id(task.id, event_id)
        console.print(f"[green]Pushed[/green] #{task.id} -> calendar event {event_id}")

    to_clean = storage.tasks_needing_event_removed()
    for task in to_clean:
        assert task.gcal_event_id is not None
        delete_event(service, task.gcal_event_id)
        storage.set_gcal_event_id(task.id, None)
        console.print(f"[green]Cleared calendar event for completed[/green] #{task.id}")

    if not to_push and not to_clean:
        console.print("[dim]Nothing to sync.[/dim]")


if __name__ == "__main__":
    app()
