from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Dict, List, Optional

from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option

from . import storage
from .calendar_sync import create_event, delete_event, get_service
from .config import TOKEN_PATH
from .dates import format_due, has_time, is_overdue, parse_due
from .models import DEFAULT_BUCKET, Task

ALL = "__all__"


class CalendarTable(DataTable):
    """Month grid that reports which cell was clicked (single click selects)."""

    class DayClicked(Message):
        def __init__(self, row: int, column: int) -> None:
            super().__init__()
            self.row, self.column = row, column

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        if meta.get("row", -1) >= 0 and meta.get("column", -1) >= 0:
            self.post_message(self.DayClicked(meta["row"], meta["column"]))


class DatePicker(ModalScreen[Optional[str]]):
    """Calendar + scrolling time lists. Dismisses with 'YYYY-MM-DD[ HH:MM]',
    '' to clear the due date, or None if cancelled."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("[", "month(-1)", "Prev month"),
        Binding("]", "month(1)", "Next month"),
        Binding("ctrl+s", "confirm", "OK"),
    ]
    NO_TIME = "none"

    def __init__(self, initial: Optional[datetime]) -> None:
        super().__init__()
        today = date.today()
        self.selected: date = initial.date() if initial else today
        self.view: date = self.selected.replace(day=1)
        self.hour: Optional[int] = initial.hour if initial and has_time(initial) else None
        self.minute: int = initial.minute if initial and has_time(initial) else 0
        self._weeks: List[List[date]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Label("Pick a due date", id="dialog-title")
            with Horizontal(id="picker-nav"):
                yield Button("◀", id="prev", compact=True)
                yield Label("", id="month-label")
                yield Button("▶", id="next", compact=True)
            with Horizontal(id="picker-body"):
                yield CalendarTable(id="cal", cursor_type="cell", zebra_stripes=False)
                with Vertical(classes="timecol"):
                    yield Label("Hour")
                    yield OptionList(id="hours")
                with Vertical(classes="timecol"):
                    yield Label("Min")
                    yield OptionList(id="mins")
            yield Label("", id="picked")
            yield Label("[dim][ ] change month · scroll the lists for a time, or leave “—” for date only.[/dim]")
            with Horizontal(id="buttons"):
                yield Button("Today", id="today")
                yield Button("Clear", id="clear")
                yield Button("OK", variant="success", id="ok")

    def on_mount(self) -> None:
        cal = self.query_one("#cal", CalendarTable)
        for name in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"):
            cal.add_column(f" {name} ", width=4)
        hours = self.query_one("#hours", OptionList)
        hours.add_option(Option("  —", id=self.NO_TIME))
        for h in range(24):
            hours.add_option(Option(f"  {h:02d}", id=str(h)))
        mins = self.query_one("#mins", OptionList)
        values = sorted(set(range(0, 60, 5)) | {self.minute})
        self._minute_values = values
        for m in values:
            mins.add_option(Option(f"  {m:02d}", id=str(m)))
        self._render_calendar()
        hours.highlighted = 0 if self.hour is None else self.hour + 1
        mins.highlighted = values.index(self.minute)
        mins.disabled = self.hour is None
        self._update_preview()
        cal.focus()

    # ---- rendering ----
    def _render_calendar(self) -> None:
        cal = self.query_one("#cal", CalendarTable)
        cal.clear()
        self._weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.view.year, self.view.month
        )
        today = date.today()
        for week in self._weeks:
            cells = []
            for d in week:
                style = ""
                if d == self.selected:
                    style = "bold reverse green"
                elif d == today:
                    style = "bold underline"
                elif d.month != self.view.month:
                    style = "dim"
                cells.append(Text(f" {d.day:>2} ", style=style, justify="center"))
            cal.add_row(*cells)
        self.query_one("#month-label", Label).update(f"{self.view:%B %Y}")
        for r, week in enumerate(self._weeks):
            if self.selected in week:
                cal.move_cursor(row=r, column=week.index(self.selected))
                break
        else:
            cal.move_cursor(row=0, column=0)

    def _update_preview(self) -> None:
        time_part = f"{self.hour:02d}:{self.minute:02d}" if self.hour is not None else "no time"
        self.query_one("#picked", Label).update(
            f"[b $accent]{self.selected:%A %d %B %Y}[/]  ·  {time_part}"
        )

    def _result(self) -> str:
        out = self.selected.isoformat()
        if self.hour is not None:
            out += f" {self.hour:02d}:{self.minute:02d}"
        return out

    # ---- interaction ----
    def _pick_cell(self, row: int, column: int) -> None:
        if 0 <= row < len(self._weeks) and 0 <= column < 7:
            self.selected = self._weeks[row][column]
            if self.selected.month != self.view.month:
                self.view = self.selected.replace(day=1)
            self._render_calendar()
            self._update_preview()

    @on(CalendarTable.DayClicked)
    def _day_clicked(self, event: CalendarTable.DayClicked) -> None:
        self._pick_cell(event.row, event.column)

    @on(DataTable.CellSelected, "#cal")
    def _cell_selected(self, event: DataTable.CellSelected) -> None:
        self._pick_cell(event.coordinate.row, event.coordinate.column)

    @on(OptionList.OptionHighlighted, "#hours")
    def _hour_changed(self, event: OptionList.OptionHighlighted) -> None:
        self.hour = None if event.option.id == self.NO_TIME else int(event.option.id or 0)
        self.query_one("#mins", OptionList).disabled = self.hour is None
        self._update_preview()

    @on(OptionList.OptionHighlighted, "#mins")
    def _minute_changed(self, event: OptionList.OptionHighlighted) -> None:
        self.minute = int(event.option.id or 0)
        self._update_preview()

    def action_month(self, delta: int) -> None:
        month_index = self.view.year * 12 + self.view.month - 1 + delta
        self.view = date(month_index // 12, month_index % 12 + 1, 1)
        if (self.selected.year, self.selected.month) != (self.view.year, self.view.month):
            # keep the same day-of-month when possible so the highlight follows
            last = calendar.monthrange(self.view.year, self.view.month)[1]
            self.selected = self.view.replace(day=min(self.selected.day, last))
        self._render_calendar()
        self._update_preview()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        self.dismiss(self._result())

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "prev":
            self.action_month(-1)
        elif bid == "next":
            self.action_month(1)
        elif bid == "today":
            self.selected = date.today()
            self.view = self.selected.replace(day=1)
            self._render_calendar()
            self._update_preview()
        elif bid == "clear":
            self.dismiss("")
        elif bid == "ok":
            self.action_confirm()


class TaskForm(ModalScreen[Optional[Dict[str, str]]]):
    """Popup form used for both adding and editing a task."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
        Binding("f2", "pick_date", "Pick date"),
    ]

    def __init__(
        self, heading: str, title: str = "", due: str = "", bucket: str = "", notes: str = ""
    ) -> None:
        super().__init__()
        self.heading = heading
        self._title, self._due, self._bucket, self._notes = title, due, bucket, notes

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.heading, id="dialog-title")
            yield Label("Title")
            yield Input(self._title, placeholder="What needs to be done", id="f-title")
            yield Label("Due  [dim](type it, or F2 to pick · optional)[/dim]")
            with Horizontal(id="due-row"):
                yield Input(self._due, placeholder="2026-10-15 18:00", id="f-due")
                yield Button("📅 Pick", id="pick-date")
            yield Label("Bucket")
            yield Input(self._bucket, placeholder=DEFAULT_BUCKET, id="f-bucket")
            yield Label("Notes  [dim](Ctrl+S to save)[/dim]")
            yield TextArea(self._notes, id="f-notes")
            yield Label("", id="form-error")
            with Horizontal(id="buttons"):
                yield Button("Save", variant="success", id="save")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#f-title", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self._save()

    def action_pick_date(self) -> None:
        due_input = self.query_one("#f-due", Input)
        try:
            initial = parse_due(due_input.value)
        except ValueError:
            initial = None

        def done(result: Optional[str]) -> None:
            if result is not None:
                due_input.value = result

        self.app.push_screen(DatePicker(initial), done)

    @on(Button.Pressed, "#pick-date")
    def _pick_date_pressed(self) -> None:
        self.action_pick_date()

    @on(Input.Submitted)
    def _submitted(self) -> None:
        self._save()

    @on(Button.Pressed, "#save")
    def _save_pressed(self) -> None:
        self._save()

    @on(Button.Pressed, "#cancel")
    def _cancel_pressed(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        title = self.query_one("#f-title", Input).value.strip()
        due = self.query_one("#f-due", Input).value.strip()
        bucket = self.query_one("#f-bucket", Input).value.strip().lower() or DEFAULT_BUCKET
        error = self.query_one("#form-error", Label)
        if not title:
            error.update("[red]Title is required[/red]")
            return
        try:
            parse_due(due)
        except ValueError as exc:
            error.update(f"[red]{exc}[/red]")
            return
        notes = self.query_one("#f-notes", TextArea).text.strip()
        self.dismiss({"title": title, "due": due, "bucket": bucket, "notes": notes})


class Confirm(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", "No"), Binding("y", "yes", "Yes"), Binding("n", "no", "No")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.message, id="dialog-title")
            with Horizontal(id="buttons"):
                yield Button("Yes (y)", variant="error", id="yes")
                yield Button("No (n)", id="no")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class TaskTable(DataTable):
    """Task table that reports double-clicks on its checkbox column."""

    class CheckboxClicked(Message):
        def __init__(self, row: int) -> None:
            super().__init__()
            self.row = row

    def on_click(self, event: events.Click) -> None:
        if event.chain != 2:  # double-click only, to avoid accidental ticks
            return
        meta = event.style.meta
        if meta.get("column") == 0 and meta.get("row", -1) >= 0:
            self.post_message(self.CheckboxClicked(meta["row"]))


class TodoApp(App):
    TITLE = "term-todo"
    SUB_TITLE = "your tasks, bucketed"

    CSS = """
    Screen { background: $surface; }
    #sidebar {
        width: 28;
        border-right: tall $primary-darken-2;
        background: $boost;
        padding: 0 1;
    }
    #sidebar-title { color: $accent; text-style: bold; padding: 1 0 0 1; }
    #buckets { background: transparent; border: none; padding: 0; margin-top: 1; }
    #main { padding: 0 1; }
    #stats { height: 3; padding: 1 1 0 1; color: $text-muted; }
    #detail {
        height: auto; max-height: 10; min-height: 3;
        border: round $primary-darken-1; padding: 0 1; margin: 0 0 1 0;
    }
    #empty { content-align: center middle; height: 1fr; color: $text-muted; display: none; }
    DataTable { height: 1fr; background: transparent; }
    DataTable > .datatable--header { background: $primary-darken-2; color: $text; text-style: bold; }
    DataTable > .datatable--cursor { background: $accent 40%; color: $text; text-style: bold; }
    TaskForm, Confirm, DatePicker { align: center middle; background: $background 60%; }
    #dialog {
        width: 72;
        height: auto;
        border: round $accent;
        background: $panel;
        padding: 1 2;
    }
    #dialog-title { text-style: bold; color: $accent; padding-bottom: 1; }
    #dialog Input { margin-bottom: 1; }
    #due-row { height: auto; margin-bottom: 1; }
    #due-row Input { width: 1fr; margin-bottom: 0; }
    #due-row Button { margin-left: 1; }
    #picker {
        width: 62; height: auto;
        border: round $accent; background: $panel; padding: 1 2;
    }
    #picker-nav { height: 1; margin-bottom: 1; }
    #picker-nav Button { min-width: 5; }
    #month-label { width: 1fr; text-align: center; text-style: bold; }
    #picker-body { height: 9; }
    #cal { width: 32; height: 9; background: transparent; }
    .timecol { width: 12; margin-left: 2; height: 9; }
    .timecol Label { color: $text-muted; text-style: bold; }
    .timecol OptionList { height: 8; }
    #picked { margin-top: 1; height: 1; }
    #f-notes { height: 6; margin-bottom: 1; }
    #buttons { height: auto; align-horizontal: right; }
    #buttons Button { margin-left: 2; }
    #form-error { height: auto; }
    """

    BINDINGS = [
        Binding("a", "add", "Add"),
        Binding("e", "edit", "Edit"),
        Binding("space", "toggle_done", "Done/Undo"),
        Binding("x", "delete", "Delete"),
        Binding("h", "toggle_hidden", "Show done"),
        Binding("s", "sync", "Sync"),
        Binding("tab", "focus_next", "Switch pane", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_bucket: str = ALL
        self.show_done = False
        self.tasks: List[Task] = []

    # ---- layout ----
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Static("BUCKETS", id="sidebar-title")
                yield OptionList(id="buckets")
            with Vertical(id="main"):
                yield Static("", id="stats")
                yield TaskTable(id="tasks", cursor_type="row", zebra_stripes=True)
                yield Static("", id="detail")
                yield Static("Nothing here yet.\nPress [b]a[/b] to add a task.", id="empty")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tasks", DataTable)
        table.add_column("", width=4)
        table.add_column("Task")
        table.add_column("Bucket", width=12)
        table.add_column("", width=3)
        table.add_column("Due", width=18)
        table.add_column("Cal", width=4)
        self.refresh_all()
        table.focus()

    # ---- data -> widgets ----
    def refresh_all(self, keep_task_id: Optional[int] = None) -> None:
        self._refresh_buckets()
        self._refresh_table(keep_task_id)

    def _refresh_buckets(self) -> None:
        counts = dict(storage.bucket_counts())
        total = sum(counts.values())
        names = sorted(counts)
        if self.current_bucket != ALL and self.current_bucket not in names:
            self.current_bucket = ALL
        ol = self.query_one("#buckets", OptionList)
        ol.clear_options()
        ol.add_option(Option(f"◆ All  [dim]{total}[/dim]", id=ALL))
        for n in names:
            ol.add_option(Option(f"  {n}  [dim]{counts[n]}[/dim]", id=n))
        ids = [ALL] + names
        ol.highlighted = ids.index(self.current_bucket)

    def _refresh_table(self, keep_task_id: Optional[int] = None) -> None:
        bucket = None if self.current_bucket == ALL else self.current_bucket
        self.tasks = storage.list_tasks(include_done=self.show_done, bucket=bucket)
        table = self.query_one("#tasks", DataTable)
        table.clear()
        now = datetime.now()
        for t in self.tasks:
            if t.done:
                mark, title = Text("☑", style="bold green"), Text(t.title, style="dim strike")
            else:
                mark, title = Text("☐", style="bold yellow"), Text(t.title)
            if t.due:
                style = "bold red" if (is_overdue(t.due, now) and not t.done) else ""
                due = Text(format_due(t.due), style=style)
            else:
                due = Text("—", style="dim")
            cal = Text("✓", style="cyan") if t.gcal_event_id else Text("", style="dim")
            note = Text("✎", style="magenta") if t.notes else Text("")
            table.add_row(mark, title, Text(t.bucket, style="cyan"), note, due, cal, key=str(t.id))
        if keep_task_id is not None:
            for i, t in enumerate(self.tasks):
                if t.id == keep_task_id:
                    table.move_cursor(row=i)
                    break

        label = "All buckets" if bucket is None else bucket
        pending = sum(1 for t in self.tasks if not t.done)
        overdue = sum(
            1 for t in self.tasks if t.due and is_overdue(t.due, now) and not t.done
        )
        extra = f"  [red]{overdue} overdue[/red]" if overdue else ""
        hidden = "" if self.show_done else "  [dim](done hidden — h)[/dim]"
        self.query_one("#stats", Static).update(
            f"[b $accent]{label}[/]  {pending} pending{extra}{hidden}"
        )
        self.query_one("#empty").display = not self.tasks
        table.display = bool(self.tasks)
        self._update_detail()

    def _update_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        task = self._selected()
        detail.display = task is not None
        if task:
            detail.border_title = f"#{task.id} · {task.title}"
            detail.update(Text(task.notes) if task.notes else Text("No notes — press e to add some", style="dim"))

    def _selected(self) -> Optional[Task]:
        table = self.query_one("#tasks", DataTable)
        if not self.tasks or table.row_count == 0:
            return None
        idx = table.cursor_row
        return self.tasks[idx] if 0 <= idx < len(self.tasks) else None

    # ---- events ----
    @on(DataTable.RowHighlighted, "#tasks")
    def _row_highlighted(self) -> None:
        self._update_detail()

    @on(OptionList.OptionHighlighted, "#buckets")
    def _bucket_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id and event.option.id != self.current_bucket:
            self.current_bucket = event.option.id
            self._refresh_table()

    @on(OptionList.OptionSelected, "#buckets")
    def _bucket_selected(self) -> None:
        self.query_one("#tasks", DataTable).focus()

    @on(TaskTable.CheckboxClicked)
    def _checkbox_clicked(self, event: TaskTable.CheckboxClicked) -> None:
        if 0 <= event.row < len(self.tasks):
            task = self.tasks[event.row]
            storage.set_done(task.id, not task.done)
            self.refresh_all(keep_task_id=task.id)

    # ---- actions ----
    def action_add(self) -> None:
        bucket = "" if self.current_bucket == ALL else self.current_bucket

        def done(result: Optional[Dict[str, str]]) -> None:
            if not result:
                return
            task = storage.add_task(
                result["title"], parse_due(result["due"]), result["bucket"], result["notes"]
            )
            self.current_bucket = task.bucket if self.current_bucket != ALL else ALL
            self.refresh_all(keep_task_id=task.id)
            self.notify(f"Added #{task.id} to {task.bucket}")

        self.push_screen(TaskForm("New task", bucket=bucket), done)

    def action_edit(self) -> None:
        task = self._selected()
        if not task:
            return
        due = task.due.strftime("%Y-%m-%d %H:%M" if has_time(task.due) else "%Y-%m-%d") if task.due else ""

        def done(result: Optional[Dict[str, str]]) -> None:
            if not result:
                return
            new_due = parse_due(result["due"])
            if task.gcal_event_id and (new_due != task.due or result["title"] != task.title
                                       or result["bucket"] != task.bucket):
                # Event is now stale: drop it so the next sync recreates it.
                self._drop_event(task)
            storage.update_task(
                task.id, result["title"], new_due, result["bucket"], result["notes"]
            )
            self.refresh_all(keep_task_id=task.id)
            self.notify(f"Updated #{task.id}")

        self.push_screen(
            TaskForm("Edit task", title=task.title, due=due, bucket=task.bucket, notes=task.notes), done
        )

    def _drop_event(self, task: Task) -> None:
        try:
            if task.gcal_event_id and TOKEN_PATH.exists():
                delete_event(get_service(), task.gcal_event_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Couldn't remove calendar event: {exc}", severity="warning")
        storage.set_gcal_event_id(task.id, None)

    def action_toggle_done(self) -> None:
        task = self._selected()
        if not task:
            return
        storage.set_done(task.id, not task.done)
        self.refresh_all(keep_task_id=task.id)

    def action_delete(self) -> None:
        task = self._selected()
        if not task:
            return

        def done(ok: Optional[bool]) -> None:
            if not ok:
                return
            if task.gcal_event_id:
                self._drop_event(task)
            storage.delete_task(task.id)
            self.refresh_all()
            self.notify(f"Deleted #{task.id}")

        self.push_screen(Confirm(f"Delete “{task.title}”?"), done)

    def action_toggle_hidden(self) -> None:
        self.show_done = not self.show_done
        self._refresh_table()

    def action_sync(self) -> None:
        if not TOKEN_PATH.exists():
            self.notify(
                "Not signed in to Google yet. Run `term-todo sync` once in a shell.",
                severity="warning",
                timeout=8,
            )
            return
        self.notify("Syncing with Google Calendar…")
        self._run_sync()

    @work(thread=True)
    def _run_sync(self) -> None:
        try:
            service = get_service()
            pushed = cleared = 0
            for t in storage.tasks_needing_push():
                assert t.due is not None
                eid = create_event(service, f"[{t.bucket}] {t.title}", t.due)
                storage.set_gcal_event_id(t.id, eid)
                pushed += 1
            for t in storage.tasks_needing_event_removed():
                assert t.gcal_event_id is not None
                delete_event(service, t.gcal_event_id)
                storage.set_gcal_event_id(t.id, None)
                cleared += 1
            msg = f"Sync done: {pushed} pushed, {cleared} cleared"
            self.call_from_thread(self.notify, msg)
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(self.notify, f"Sync failed: {exc}", severity="error")
        self.call_from_thread(self._refresh_table)


def run() -> None:
    TodoApp().run()
