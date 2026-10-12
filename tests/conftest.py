"""Test setup: point term-todo at a throwaway data directory *before* it is imported."""
import os
import tempfile

_HOME = tempfile.mkdtemp(prefix="term-todo-test-")
os.environ["TERM_TODO_HOME"] = _HOME

import pytest  # noqa: E402

from term_todo import storage  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own empty database."""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "todos.db")
    return tmp_path / "todos.db"
