# term-todo

A terminal to-do list that can sync tasks with Google Calendar, so a due
task also shows up (and reminds you) on your calendar.

Tasks are stored locally in a SQLite database at `~/.term-todo/todos.db`.
Running `term-todo sync` pushes any pending task that has a due date to
your primary Google Calendar as an event with a popup reminder, and
removes the calendar event once you mark the task done.

## Install

```bash
git clone https://github.com/bocho0600/term-todo.git
cd term-todo
pip install -e .
```

This installs the `term-todo` command.

## Usage

```bash
# Add a task
term-todo add "Submit report" --due "2026-10-15 18:00"

# Add a task with no due date (never synced to Calendar)
term-todo add "Read a book"

# List pending tasks
term-todo list

# Include completed tasks
term-todo list --all

# Mark a task done
term-todo done 1

# Delete a task (also removes its Calendar event, if any)
term-todo rm 2

# Push due tasks to Google Calendar / clean up completed ones
term-todo sync

# Set a different reminder lead time (minutes before due)
term-todo sync --reminder 15
```

Due dates accept `YYYY-MM-DD HH:MM`, `YYYY-MM-DD`, `DD/MM/YYYY HH:MM`, or
`DD/MM/YYYY`.

## Google Calendar setup

`term-todo sync` needs a one-time OAuth client so it can create events on
your behalf.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/),
   create (or pick) a project, and enable the **Google Calendar API**
   (APIs & Services → Library).
2. Go to APIs & Services → Credentials → **Create Credentials** →
   **OAuth client ID**. Choose **Desktop app** as the application type.
3. Download the resulting JSON and save it as:

   ```text
   ~/.term-todo/credentials.json
   ```

4. Run `term-todo sync`. The first run opens a browser window asking you
   to sign in and grant access; after that, a token is cached at
   `~/.term-todo/token.json` so you won't need to log in again.

`credentials.json` and `token.json` are both secrets specific to your
machine — they're excluded via `.gitignore` and should never be committed.

### Changing where files are stored

Set `TERM_TODO_HOME` to use a different directory for the database,
`credentials.json`, and `token.json` (defaults to `~/.term-todo`):

```bash
export TERM_TODO_HOME="$HOME/.config/term-todo"
```

## Roadmap

- Two-way sync (pull changes made directly in Google Calendar back into
  term-todo)
- Recurring tasks
- Local desktop notifications in addition to Calendar reminders
