import os
from pathlib import Path

APP_DIR = Path(os.environ.get("TERM_TODO_HOME", Path.home() / ".term-todo"))
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DIR / "todos.db"
CREDENTIALS_PATH = APP_DIR / "credentials.json"
TOKEN_PATH = APP_DIR / "token.json"
