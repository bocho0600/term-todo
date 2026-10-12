from datetime import datetime

from term_todo.models import Task
from term_todo.tray import SIZE, _esc, _task_label, render_icon


def test_icon_is_square_argb():
    for count in (0, 1, 7, 42, 100, 5000):
        assert len(render_icon(count)) == SIZE * SIZE * 4


def test_icon_differs_by_count_and_has_ink():
    zero, one, two = render_icon(0), render_icon(1), render_icon(2)
    assert zero != one != two
    assert any(b for b in one)  # not blank


def test_menu_label_escaping():
    assert _esc("snake_case") == "snake__case"


def _task(**kw):
    base = dict(id=1, title="t", due=None, done=False, gcal_event_id=None,
                created_at=datetime(2026, 1, 1), bucket="b", notes="")
    base.update(kw)
    return Task(**base)


def test_task_label_marks_overdue_notes_and_truncates():
    now = datetime(2026, 10, 16, 12, 0)
    overdue = _task(title="x" * 80, due=datetime(2026, 10, 1, 9, 0), notes="n")
    label = _task_label(overdue, now)
    assert "⚠" in label and "✎" in label and "…" in label

    today = _task_label(_task(due=datetime(2026, 10, 16)), now)  # date-only, due today
    assert "⚠" not in today and "Fri 16 Oct" in today and "00:00" not in today
