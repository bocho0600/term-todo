from datetime import datetime

import pytest

from term_todo.dates import format_due, has_time, is_overdue, parse_due


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-10-15 18:00", datetime(2026, 10, 15, 18, 0)),
        ("2026-10-15", datetime(2026, 10, 15)),
        ("15/10/2026 18:30", datetime(2026, 10, 15, 18, 30)),
        ("15/10/2026", datetime(2026, 10, 15)),
        ("  2026-10-15  ", datetime(2026, 10, 15)),
    ],
)
def test_parse_due_formats(text, expected):
    assert parse_due(text) == expected


@pytest.mark.parametrize("text", [None, "", "   "])
def test_parse_due_empty_is_none(text):
    assert parse_due(text) is None


@pytest.mark.parametrize("text", ["tomorrow", "2026-13-40", "15-10-2026", "18:00"])
def test_parse_due_invalid(text):
    with pytest.raises(ValueError):
        parse_due(text)


def test_has_time():
    assert has_time(datetime(2026, 10, 15, 9, 5))
    assert not has_time(datetime(2026, 10, 15))


def test_format_due():
    assert format_due(datetime(2026, 10, 16)) == "Fri 16 Oct"
    assert format_due(datetime(2026, 10, 16, 14, 30)) == "Fri 16 Oct 14:30"
    assert format_due(datetime(2026, 10, 16), short=False) == "2026-10-16"
    assert format_due(datetime(2026, 10, 16, 14, 30), short=False) == "2026-10-16 14:30"


def test_overdue_timed_task():
    now = datetime(2026, 10, 16, 12, 0)
    assert is_overdue(datetime(2026, 10, 16, 11, 59), now)
    assert not is_overdue(datetime(2026, 10, 16, 12, 1), now)


def test_date_only_task_not_overdue_until_day_has_passed():
    due = datetime(2026, 10, 16)
    assert not is_overdue(due, datetime(2026, 10, 16, 23, 59))
    assert is_overdue(due, datetime(2026, 10, 17, 0, 1))
