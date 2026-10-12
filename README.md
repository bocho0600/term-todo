# term-todo

A fast, keyboard-and-mouse friendly to-do list for your terminal — with
buckets, per-task notes, a full-screen UI with a calendar date picker, a
system-tray counter, and optional one-way sync to Google Calendar.

- **Buckets** – group tasks by project (`work`, `personal`, …); anything
  unsorted lands in `inbox`.
- **Notes** – attach free-form notes to any task.
- **Terminal UI** – bucket sidebar, task table, notes panel, popup forms, and a
  calendar + scrolling-time picker for due dates.
- **Tray icon** – a panel icon showing your pending count; click it to see
  what's waiting.
- **Google Calendar sync** – due tasks become calendar events (timed events
  with a popup reminder, or all-day events when no time is set) and are
  removed when you tick the task off.
- **Local & private** – tasks live in a SQLite file on your machine.

> **Platform support:** developed and tested on Linux (Ubuntu/GNOME). The CLI,
> terminal UI and Calendar sync are plain Python and *should* work on macOS and
> Windows, but those are untested. The **tray icon is Linux-only** (desktops
> that host StatusNotifier icons: GNOME with the AppIndicator extension, KDE,
> XFCE, …).

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Command reference](#command-reference)
- [Terminal UI](#terminal-ui)
- [Tray icon (Linux)](#tray-icon-linux)
- [Google Calendar sync](#google-calendar-sync)
- [Configuration & data](#configuration--data)
- [Updating & uninstalling](#updating--uninstalling)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Roadmap](#roadmap)

## Install

Requires **Python 3.9+**.

### Recommended: pipx

[pipx](https://pipx.pypa.io/) installs the app in its own isolated environment
and puts `term-todo` on your `PATH`, so it works from any directory with no
virtualenv to activate.

```bash
# one-time: install pipx (Debian/Ubuntu shown; see pipx docs for other systems)
sudo apt install pipx && pipx ensurepath      # then open a new terminal

pipx install git+https://github.com/bocho0600/term-todo
term-todo --help
```

**Want the tray icon too?** It needs your system's PyGObject, so install with
access to system packages:

```bash
sudo apt install python3-gi                    # usually already present on Ubuntu
pipx install --system-site-packages git+https://github.com/bocho0600/term-todo
```

### Alternative: a plain virtualenv

If you'd rather not use pipx:

```bash
python3 -m venv --system-site-packages ~/.local/share/term-todo/venv
~/.local/share/term-todo/venv/bin/pip install git+https://github.com/bocho0600/term-todo
mkdir -p ~/.local/bin
ln -sf ~/.local/share/term-todo/venv/bin/term-todo ~/.local/bin/term-todo
```

Make sure `~/.local/bin` is on your `PATH`. (`--system-site-packages` is only
needed for the tray icon; drop it if you don't want that.)

### From a clone

```bash
git clone https://github.com/bocho0600/term-todo.git
cd term-todo
pipx install .          # or: pip install .
```

## Quick start

```bash
term-todo add "Submit report" -b work -d "2026-10-15 18:00" -n "attach the appendix"
term-todo add "Read a book"          # no bucket -> "inbox", no due date
term-todo list                       # everything pending, grouped by bucket
term-todo ui                         # open the full-screen UI
```

## Command reference

| Command | What it does |
|---|---|
| `term-todo add TITLE [-b BUCKET] [-d DUE] [-n NOTE]` | Add a task. |
| `term-todo list [-b BUCKET] [--all]` | List pending tasks (add `--all` for completed too). |
| `term-todo buckets` | Show every bucket with its pending count. |
| `term-todo mv ID BUCKET` | Move a task to another bucket. |
| `term-todo note ID [TEXT] [--clear]` | Show a task's notes, append a line, or clear them. |
| `term-todo done ID` | Mark a task done. |
| `term-todo rm ID` | Delete a task (and its Calendar event, if any). |
| `term-todo sync [--reminder MIN]` | Push due tasks to Google Calendar. |
| `term-todo ui` | Open the interactive terminal UI. |
| `term-todo tray [-d] [--install-autostart] [--remove-autostart]` | Run the tray icon. |

Bucket names are case-insensitive (`Work` and `work` are the same bucket) and
are created the first time you use them.

### Due dates

Accepted formats: `YYYY-MM-DD HH:MM`, `YYYY-MM-DD`, `DD/MM/YYYY HH:MM`,
`DD/MM/YYYY`.

A due date **without a time** is *date-only*: it's shown without a clock time,
isn't overdue until the day has passed, and syncs to Google Calendar as an
**all-day event**. (Because of this, a due time of exactly `00:00` is treated
as "no time".)

## Terminal UI

```bash
term-todo ui
```

A bucket sidebar on the left, your tasks on the right, and a notes panel under
the table for the highlighted task. Overdue tasks are red, completed tasks are
struck through, and a `✎` marks tasks that have notes.

| Key | Action |
|---|---|
| `↑` `↓` | Move through buckets / tasks |
| `Tab` | Switch between sidebar and table |
| `a` | Add a task (the current bucket is pre-filled) |
| `e` | Edit the highlighted task |
| `Space` | Mark done / undo |
| *double-click* the `☐` | Mark done / undo (single clicks are ignored on purpose) |
| `x` | Delete (asks for confirmation) |
| `h` | Show / hide completed tasks |
| `s` | Sync with Google Calendar |
| `q` | Quit |

**Add / edit form:** fill in the title, due date, bucket and notes. `Ctrl+S`
saves from anywhere in the form (`Enter` saves from a single-line field; inside
the notes box `Enter` adds a new line). Press `Esc` to cancel.

**Date picker:** press `F2` (or click **📅 Pick**) in the Due field.

- Click a day, or use the arrow keys and `Enter`. `[` / `]` change month.
- Scroll the **Hour** and **Min** lists for a time. Leave the hour on `—` for a
  date-only task.
- **Today** jumps to today, **Clear** removes the due date, **OK** (or
  `Ctrl+S`) confirms, `Esc` cancels.
- You can always type the date by hand instead.

Pressing `s` syncs to Google Calendar, but only after you've done the
[one-time sign-in](#google-calendar-sync).

## Tray icon (Linux)

```bash
term-todo tray -d                     # start a panel icon in the background
term-todo tray --install-autostart    # also start it at every login
term-todo tray --remove-autostart     # undo that
```

The icon is a white box showing your pending-task count (a tick when there's
nothing left). Click it for a menu listing your tasks grouped by bucket, with
due dates, `⚠` on overdue ones and `✎` on ones with notes. Choose **Open
term-todo** to launch the UI in a terminal. It refreshes every 30 seconds.

**Requirements:** a desktop that shows StatusNotifier ("AppIndicator") icons,
and the system `python3-gi` package made visible to the install (see the
`--system-site-packages` notes under [Install](#install)). On GNOME/Ubuntu the
AppIndicator extension is normally enabled out of the box; on stock GNOME
you may need `gnome-shell-extension-appindicator`.

Only one tray icon runs at a time; starting a second just exits.

## Google Calendar sync

Syncing is **one-way** (term-todo → Google Calendar) and **manual**: run
`term-todo sync` (or press `s` in the UI) whenever you want to push changes.

- Each pending task with a due date becomes an event titled `[bucket] title`.
  - With a time: a 30-minute event with a popup reminder (default 30 minutes
    before; change it with `--reminder`).
  - Date only: an all-day event using your calendar's default reminder.
- Marking a task done removes its event on the next sync.
- Deleting a task removes its event immediately.
- Editing a synced task's title, date or bucket drops the old event; the next
  sync creates the updated one.
- Tasks with no due date are never synced.
- Notes are **not** sent to Calendar.

### One-time setup

Google requires every app to use its own OAuth client, so you create one
(free, ~5 minutes) and point term-todo at it.

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and
   create a project (or pick an existing one).
2. **Enable the API:** APIs & Services → Library → search for
   **Google Calendar API** → **Enable**.
3. **Configure the consent screen:** Google Auth Platform → set it up with
   user type **External**. Then, on the **Audience** page, add your own Google
   account under **Test users**. *(Skipping this causes "Error 403:
   access_denied" when you sign in.)*
4. **Create the credentials:** Google Auth Platform → **Clients** →
   **Create client** → application type **Desktop app**.
5. **Get the JSON:** open the client you created and, under **Client
   secrets**, use **Add secret**, then **Download JSON** *immediately* — Google
   only shows a secret once and no longer lets you download old ones. (If you
   see a "client secret" you can't download, add a new one.)
6. Save the file as `~/.term-todo/credentials.json`:

   ```bash
   mkdir -p ~/.term-todo
   mv ~/Downloads/client_secret_*.json ~/.term-todo/credentials.json
   chmod 600 ~/.term-todo/credentials.json
   ```

7. Run `term-todo sync`. A browser opens: pick your account (the one you added
   as a test user), click **Advanced → Go to term-todo (unsafe)** past the
   "unverified app" warning (it's *your* app), and allow calendar access. A
   token is cached at `~/.term-todo/token.json`, so you only sign in once.

> **Note:** while the consent screen's publishing status is **Testing**, Google
> expires the login after **7 days** and you'll be asked to sign in again. To
> avoid that, set the status to **In production** on the Audience page — for a
> personal app you do *not* need to submit it for verification; you'll just keep
> seeing the "unverified" warning when signing in.

`credentials.json` and `token.json` are secrets. They're in `.gitignore`;
never commit or share them.

## Configuration & data

Everything lives in one folder, `~/.term-todo/` by default:

| File | Contents |
|---|---|
| `todos.db` | Your tasks, buckets and notes (SQLite) |
| `credentials.json` | Your Google OAuth client (secret) |
| `token.json` | Cached Google login (secret) |

Set `TERM_TODO_HOME` to use a different folder:

```bash
export TERM_TODO_HOME="$HOME/.config/term-todo"
```

Back up or move your tasks by copying `todos.db`. Databases from older
versions are upgraded automatically the first time they're opened.

## Updating & uninstalling

```bash
# update
pipx upgrade term-todo
# (reinstall from git to pick up the newest commit)
pipx install --force git+https://github.com/bocho0600/term-todo

# uninstall
term-todo tray --remove-autostart      # if you enabled autostart
pipx uninstall term-todo
rm -rf ~/.term-todo                    # optional: deletes your tasks and credentials!
```

Installed with a plain virtualenv instead? Re-run
`~/.local/share/term-todo/venv/bin/pip install --upgrade git+https://github.com/bocho0600/term-todo`
to update, or delete `~/.local/share/term-todo` and `~/.local/bin/term-todo` to
uninstall.

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: term-todo` | Run `pipx ensurepath` and open a new terminal, or make sure `~/.local/bin` is on your `PATH`. |
| `error: externally-managed-environment` from `pip` | Use pipx or a virtualenv as shown in [Install](#install) rather than `pip install` into the system Python. |
| `Missing Google OAuth client file` | You haven't saved `~/.term-todo/credentials.json` yet — see [setup](#one-time-setup). |
| `Error 403: access_denied` when signing in | Add your Google account under **Audience → Test users** in the Cloud Console, then try again. |
| `redirect_uri_mismatch` | The OAuth client isn't type **Desktop app**; create a new Desktop client. |
| Sync worked but I can't see the event | Date-only tasks are all-day events — look in the banner at the top of that day. Tasks with no due date are never synced. |
| Asked to sign in again after about a week | The consent screen is in **Testing** mode; switch it to **In production** (see the note above), or just sign in again. |
| Sync in the UI says "Not signed in to Google yet" | Run `term-todo sync` once in a shell to complete the browser sign-in. |
| Tray icon doesn't appear | Needs a StatusNotifier-capable panel (on GNOME enable the AppIndicator extension) and `python3-gi` visible to the install. Run `term-todo tray` (without `-d`) to see any error. |
| `ModuleNotFoundError: gi` / "needs PyGObject" | `sudo apt install python3-gi`, then reinstall with `--system-site-packages`. |
| Layout looks broken or colours are off | Use a modern terminal with true-colour and Unicode support and make it at least ~100 columns wide. |

## Development

```bash
git clone https://github.com/bocho0600/term-todo.git
cd term-todo
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
term-todo --help
```

Layout: `term_todo/cli.py` (Typer commands), `ui.py` (Textual UI and date
picker), `tray.py` (StatusNotifier tray icon), `storage.py` (SQLite),
`calendar_sync.py` (Google Calendar), `dates.py` (date parsing/formatting).

## Roadmap

- Two-way sync (pull edits made in Google Calendar back into term-todo)
- Automatic background sync
- Recurring tasks
- Local desktop notifications in addition to Calendar reminders
