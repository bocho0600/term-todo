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


def test_parse_repeat():
    from term_todo.dates import parse_repeat

    assert parse_repeat(" Weekly ") == "weekly"
    assert parse_repeat("") == "" and parse_repeat(None) == "" and parse_repeat("none") == ""
    with pytest.raises(ValueError):
        parse_repeat("fortnightly")


def test_next_due_skips_missed_occurrences():
    from term_todo.dates import next_due

    now = datetime(2026, 10, 12, 9, 0)
    assert next_due(datetime(2026, 10, 12), "weekly", now) == datetime(2026, 10, 19)
    assert next_due(datetime(2026, 10, 16, 18, 0), "weekly", now) == datetime(2026, 10, 23, 18, 0)
    # three weeks overdue: jump to the next future slot, same weekday and time
    assert next_due(datetime(2026, 9, 21, 8, 30), "weekly", now) == datetime(2026, 10, 19, 8, 30)
    assert next_due(datetime(2026, 10, 12), "daily", now) == datetime(2026, 10, 13)
    assert next_due(datetime(2026, 1, 31), "monthly", datetime(2026, 1, 31)) == datetime(2026, 2, 28)
    assert next_due(datetime(2026, 12, 15), "monthly", datetime(2026, 12, 15)) == datetime(2027, 1, 15)
