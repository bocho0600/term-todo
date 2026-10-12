# term-todo

A terminal to-do list that can sync tasks with Google Calendar, so a due
task also shows up (and reminds you) on your calendar.

Tasks (with buckets and notes) are stored locally in a SQLite database at `~/.term-todo/todos.db`.
Running `term-todo sync` pushes any pending task that has a due date to
your primary Google Calendar as an event with a popup reminder, and
removes the calendar event once you mark the task done.

## Install

Install it once into its own virtualenv and link the command onto your
`PATH`, so `term-todo` works from anywhere (no activating anything):

```bash
git clone https://github.com/bocho0600/term-todo.git
cd term-todo
python3 -m venv --system-site-packages ~/.local/share/term-todo/venv
~/.local/share/term-todo/venv/bin/pip install .
ln -s ~/.local/share/term-todo/venv/bin/term-todo ~/.local/bin/term-todo
```

`--system-site-packages` lets the tray icon use your system's `python3-gi`.
To update after pulling changes, re-run the `pip install --upgrade .` line.

## Usage

```bash
# Add a task (optionally into a bucket, with a due date and notes)
term-todo add "Submit report" -b work -d "2026-10-15 18:00" -n "attach the appendix"

# Tasks with no bucket go to "inbox"; no due date means never synced
term-todo add "Read a book"

term-todo list                 # all pending tasks, grouped by bucket
term-todo list -b work       # just one bucket
term-todo list --all           # include completed
term-todo buckets              # buckets with pending counts
term-todo mv 3 personal            # move a task to another bucket

term-todo note 3               # show a task's notes
term-todo note 3 "more text"   # append a line
term-todo note 3 --clear

term-todo done 1               # mark done
term-todo rm 2                 # delete (also removes its Calendar event)

term-todo sync                 # push due tasks to Google Calendar
term-todo sync --reminder 15   # popup reminder 15 min before due
```

Due dates accept `YYYY-MM-DD HH:MM`, `YYYY-MM-DD`, `DD/MM/YYYY HH:MM`, or
`DD/MM/YYYY`. A date with no time is "date only": it shows without a time and
isn't overdue until the day has passed.

### Terminal UI

```bash
term-todo ui
```

A bucket sidebar, task table and notes panel. Keys: `a` add, `e` edit,
`Space` or double-click the checkbox to tick, `x` delete, `h` show/hide done,
`s` sync, `Tab` switch pane, `q` quit. In the add/edit form, `F2` (or the
**Pick** button) opens a calendar with scrolling hour/minute lists; leave the
time at `—` for a date-only task. `Ctrl+S` saves the form.

### Tray icon

```bash
term-todo tray -d                     # show a panel icon with your pending count
term-todo tray --install-autostart    # start it at login (--remove-autostart to undo)
```

Click the icon to see waiting tasks grouped by bucket. Needs a desktop that
hosts StatusNotifier icons (GNOME with the AppIndicator extension, KDE, ...)
and `python3-gi`.

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
