"""Headless tests for the Textual UI, driven with Textual's test pilot."""
import asyncio
from datetime import date

from textual.widgets import DataTable, Input, OptionList, TextArea

from term_todo import storage
from term_todo.ui import DatePicker, TaskForm, TodoApp


def run(coro_fn):
    asyncio.run(coro_fn())


def test_table_shows_tasks_and_bucket_counts():
    storage.add_task("one", None, "a")
    storage.add_task("two", None, "b")

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause()
            assert app.query_one("#tasks", DataTable).row_count == 2
            assert len(app.query_one("#buckets", OptionList).options) == 3  # All, a, b

    run(scenario)


def test_add_task_through_form():
    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(app.screen, TaskForm)
            await pilot.press(*"Ship it")
            app.screen.query_one("#f-bucket", Input).value = "Work"
            app.screen.query_one("#f-notes", TextArea).text = "line1\nline2"
            await pilot.press("ctrl+s")
            await pilot.pause()

    run(scenario)
    (task,) = storage.list_tasks()
    assert (task.title, task.bucket, task.notes) == ("Ship it", "work", "line1\nline2")


def test_form_requires_title_and_valid_due():
    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("ctrl+s")  # no title
            await pilot.pause()
            assert isinstance(app.screen, TaskForm)
            await pilot.press(*"x")
            app.screen.query_one("#f-due", Input).value = "garbage"
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert isinstance(app.screen, TaskForm)  # still open

    run(scenario)
    assert storage.list_tasks() == []


def test_space_toggles_done_and_h_shows_completed():
    storage.add_task("t", None)

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            assert app.query_one("#tasks", DataTable).row_count == 0
            await pilot.press("h")
            await pilot.pause()
            assert app.query_one("#tasks", DataTable).row_count == 1

    run(scenario)
    assert storage.get_task(1).done


def test_only_double_click_ticks_checkbox():
    storage.add_task("t", None)

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause()
            await pilot.click("#tasks", offset=(1, 1))
            await pilot.pause()
            assert not storage.get_task(1).done  # single click ignored
            await pilot.click("#tasks", offset=(1, 1), times=2)
            await pilot.pause()
            assert storage.get_task(1).done
            await pilot.click("#tasks", offset=(12, 1), times=2)  # title column: no toggle
            await pilot.pause()
            assert storage.get_task(1).done

    run(scenario)


def test_delete_asks_for_confirmation():
    storage.add_task("t", None)

    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause()
            await pilot.press("x")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            assert storage.get_task(1) is not None
            await pilot.press("x")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

    run(scenario)
    assert storage.get_task(1) is None


def test_date_picker_with_time():
    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 42)) as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.press(*"Dentist")
            await pilot.press("f2")
            await pilot.pause()
            picker = app.screen
            assert isinstance(picker, DatePicker)
            assert picker.selected == date.today() and picker.hour is None
            picker.query_one("#hours", OptionList).focus()
            await pilot.press(*(["down"] * 15))  # "—", 00 ... -> 14
            picker.query_one("#mins", OptionList).focus()
            await pilot.press(*(["down"] * 6))  # 00,05 ... -> 30
            assert (picker.hour, picker.minute) == (14, 30)
            await pilot.press("ctrl+s")
            await pilot.pause()
            expected = f"{date.today().isoformat()} 14:30"
            assert app.screen.query_one("#f-due", Input).value == expected
            await pilot.press("ctrl+s")
            await pilot.pause()

    run(scenario)
    (task,) = storage.list_tasks()
    assert (task.due.hour, task.due.minute) == (14, 30)


def test_date_picker_without_time_is_date_only():
    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 42)) as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.press(*"All day")
            await pilot.press("f2")
            await pilot.pause()
            await pilot.press("ctrl+s")  # accept today, leave time at "—"
            await pilot.pause()
            assert app.screen.query_one("#f-due", Input).value == date.today().isoformat()
            await pilot.press("ctrl+s")
            await pilot.pause()

    run(scenario)
    (task,) = storage.list_tasks()
    assert task.due.date() == date.today() and (task.due.hour, task.due.minute) == (0, 0)


def test_date_picker_month_navigation_and_clear():
    async def scenario():
        app = TodoApp()
        async with app.run_test(size=(110, 42)) as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.press(*"x")
            app.screen.query_one("#f-due", Input).value = "2026-01-31"
            await pilot.press("f2")
            await pilot.pause()
            picker = app.screen
            assert picker.selected == date(2026, 1, 31)
            await pilot.press("]")
            await pilot.pause()
            assert picker.selected == date(2026, 2, 28)  # day clamps to month length
            await pilot.press("[")
            await pilot.pause()
            assert picker.view == date(2026, 1, 1)
            await pilot.click("#clear")
            await pilot.pause()
            assert app.screen.query_one("#f-due", Input).value == ""

    run(scenario)
