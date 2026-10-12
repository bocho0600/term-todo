from datetime import datetime

from term_todo.calendar_sync import build_event_body


def test_timed_event():
    body = build_event_body("[work] t", datetime(2026, 10, 16, 14, 30), reminder_minutes=15)
    assert body["summary"] == "[work] t"
    assert body["start"]["dateTime"].startswith("2026-10-16T14:30:00")
    assert body["end"]["dateTime"].startswith("2026-10-16T15:00:00")
    assert body["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 15}],
    }


def test_date_only_becomes_all_day_event():
    body = build_event_body("t", datetime(2026, 10, 16))
    assert body["start"] == {"date": "2026-10-16"}
    assert body["end"] == {"date": "2026-10-17"}  # end date is exclusive
    assert body["reminders"] == {"useDefault": True}


def test_all_day_event_crosses_month_end():
    body = build_event_body("t", datetime(2026, 10, 31))
    assert body["end"] == {"date": "2026-11-01"}
