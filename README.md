<h1 align="center">
  <img src="https://raw.githubusercontent.com/bocho0600/term-todo/main/assets/banner.svg" alt="term-todo" width="640">
</h1>

<p align="center">
  <a href="https://github.com/bocho0600/term-todo/actions/workflows/ci.yml"><img src="https://github.com/bocho0600/term-todo/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-3776ab.svg" alt="Python 3.9+">
</p>

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
- **Sync across machines** – sign in with Google and your tasks follow you to every
  computer, stored privately in your own Google account (no server, no extra service).
- **Google Calendar sync** – due tasks become calendar events (timed events
  with a popup reminder, or all-day events when no time is set) and are
  removed when you tick the task off.
- **Local & private** – tasks live in a SQLite file on your machine.

<p align="center">
  <img src="https://raw.githubusercontent.com/bocho0600/term-todo/main/assets/demo.svg" alt="term-todo demo: adding tasks, listing them and syncing to Google Calendar" width="720">
</p>

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
- [Sign in & sync across machines](#sign-in--sync-across-machines)
- [Google Calendar sync](#google-calendar-sync)
- [Google setup (one time)](#google-setup-one-time)
- [Configuration & data](#configuration--data)
- [Updating & uninstalling](#updating--uninstalling)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Releasing](#releasing)
- [Roadmap](#roadmap)
- [License](#license)

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
| `term-todo login` | Sign in with Google (enables cross-machine sync and Calendar). |
| `term-todo logout` | Sign out on this machine (local tasks are kept). |
| `term-todo sync [--reminder MIN]` | Merge tasks with your other machines, then push due tasks to Google Calendar. |
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

## Sign in & sync across machines

Use term-todo on more than one computer and keep one task list. Sign in with the
same Google account on each machine and your tasks (buckets, notes, due dates,
done state) are merged through a small file in your Google Drive.

- **Private by design.** The file lives in Drive's hidden *app data* folder. It
  doesn't appear in your Drive, no other app can read it, and term-todo can't
  see anything else in your Drive. There is no term-todo server.
- **Works offline.** Everything is stored locally first; changes sync when you
  next have a connection.

### Set it up

1. Do the [Google setup](#google-setup-one-time) once (it includes enabling the
   **Google Drive API**).
2. On each machine, install term-todo and put the OAuth client file at
   `~/.term-todo/credentials.json`. On a second machine the easiest way is to
   copy it from the first:

   ```bash
   mkdir -p ~/.term-todo
   scp first-machine:~/.term-todo/credentials.json ~/.term-todo/
   chmod 600 ~/.term-todo/credentials.json
   ```

3. Sign in:

   ```bash
   term-todo login
   ```

   A browser opens; choose the same Google account on every machine. The first
   login also uploads or downloads your tasks, so a new machine immediately gets
   your list.

### How it behaves

- **Automatic in the UI.** `term-todo ui` syncs when it opens, a few seconds
  after each change you make, and once more when you quit. The header shows
  `☁ synced 14:05` (or `☁ offline` if it couldn't reach Google).
- **Automatic in the tray.** The tray icon syncs every few minutes, so its count
  stays current.
- **On demand from the CLI.** Plain commands like `add` and `done` only change
  this machine; run `term-todo sync` to push them. (`term-todo sync` also
  updates Google Calendar.)
- **Conflicts:** if the same task was edited on two machines, the most recent
  edit wins. Deleting a task on one machine deletes it everywhere.
- **Task numbers are per machine.** The `#id` shown in `list` may differ between
  computers, so use titles (or the UI) rather than ids when talking across
  machines.
- **Calendar events are shared.** Once one machine has pushed a task to Google
  Calendar, the others know about the event and won't create a duplicate.
- **Signing out:** `term-todo logout` forgets the login on this machine and keeps
  your local tasks. It doesn't delete the cloud copy; to remove that, go to
  Google Drive → Settings → Manage apps → term-todo → *Delete hidden app data*.

## Google Calendar sync

Calendar sync is **one-way** (term-todo → Google Calendar) and **manual**: run
`term-todo sync` (or press `s` in the UI) whenever you want to push changes.
(Task syncing between machines, above, is separate and automatic in the UI.)

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

Setting up Google access is described in [Google setup](#google-setup-one-time).

## Google setup (one time)

Google requires every app to use its own OAuth client, so you create one (free,
about 5 minutes) and point term-todo at it. The same client is used on all your
machines.

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and
   create a project (or pick an existing one).
2. **Enable the APIs:** APIs & Services → Library → enable both the
   **Google Calendar API** and the **Google Drive API** (Drive is used only for
   the hidden sync file). Skip Drive if you only want Calendar.
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

7. Run `term-todo login`. A browser opens: pick your account (the one you added
   as a test user), click **Advanced → Go to term-todo (unsafe)** past the
   "unverified app" warning (it's *your* app), and allow access (Google Calendar, plus Drive "app data" for sync). A
   token is cached at `~/.term-todo/token.json`, so you only sign in once per
   machine.

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
| `Missing Google OAuth client file` | You haven't saved `~/.term-todo/credentials.json` yet — see [Google setup](#google-setup-one-time). On a second machine, copy it from your first. |
| `Error 403: access_denied` when signing in | Add your Google account under **Audience → Test users** in the Cloud Console, then try again. |
| `redirect_uri_mismatch` | The OAuth client isn't type **Desktop app**; create a new Desktop client. |
| Sync worked but I can't see the event | Date-only tasks are all-day events — look in the banner at the top of that day. Tasks with no due date are never synced. |
| Asked to sign in again after about a week | The consent screen is in **Testing** mode; switch it to **In production** (see the note above), or just sign in again. |
| Sync in the UI says "Not signed in to Google yet" | Run `term-todo login` once in a shell to complete the browser sign-in. |
| `Cloud sync skipped: The Google Drive API isn't enabled…` | Enable the **Google Drive API** for your project (link is in the message), wait a minute, run `term-todo sync` again. |
| `Cloud sync skipped: Not signed in` / asked to sign in again | Run `term-todo login`. (An expired or revoked login needs this too.) |
| Tasks from my other machine don't show up | Both machines must use the **same Google account**. Run `term-todo sync` on the machine that has the tasks, then on the other (the UI does this automatically). |
| Cloud data was written by a newer term-todo | Upgrade this machine: `pipx upgrade term-todo`. |
| Tray icon doesn't appear | Needs a StatusNotifier-capable panel (on GNOME enable the AppIndicator extension) and `python3-gi` visible to the install. Run `term-todo tray` (without `-d`) to see any error. |
| `ModuleNotFoundError: gi` / "needs PyGObject" | `sudo apt install python3-gi`, then reinstall with `--system-site-packages`. |
| Layout looks broken or colours are off | Use a modern terminal with true-colour and Unicode support and make it at least ~100 columns wide. |

## Development

```bash
git clone https://github.com/bocho0600/term-todo.git
cd term-todo
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
term-todo --help
```

Run the checks (the same ones CI runs on every push and pull request):

```bash
ruff check .      # lint
pytest -q         # test suite
python -m build && twine check dist/*   # packaging sanity check
```

The tests use a throwaway data directory, so they never touch your real tasks.
The UI tests drive the Textual app headlessly. CI runs the suite on Python
3.9 through 3.13.

Layout: `term_todo/cli.py` (Typer commands), `ui.py` (Textual UI and date
picker), `tray.py` (StatusNotifier tray icon), `storage.py` (SQLite),
`calendar_sync.py` (Google Calendar), `dates.py` (date parsing/formatting);
`tests/` mirrors those modules. The animated README art in `assets/` is generated
by `python3 scripts/gen_assets.py` — edit that script, not the SVGs.

## Releasing

Releases are published to [PyPI](https://pypi.org/) by GitHub Actions when you
push a version tag. It uses PyPI *trusted publishing*, so no API token is
stored anywhere.

**One-time setup (maintainer):**

1. Create a PyPI account, then add a *pending publisher* at
   <https://pypi.org/manage/account/publishing/> with: project name
   `term-todo`, owner `bocho0600`, repository `term-todo`, workflow
   `release.yml`, environment `pypi`.
2. In the GitHub repo: Settings → Environments → create an environment named
   `pypi` (optionally require your approval for deployments).

**Each release:**

```bash
# 1. bump `version` in pyproject.toml and commit it
# 2. tag it (the tag must be "v" + the version) and push
git tag v0.2.0
git push origin v0.2.0
```

The workflow runs the tests, builds the package, publishes it to PyPI and
creates a GitHub Release with the build attached. Once the first release is
live, users can install with `pipx install term-todo`.

## Roadmap

- Two-way sync (pull edits made in Google Calendar back into term-todo)
- Optional automatic cloud sync for plain CLI commands (`add`, `done`, …)
- Recurring tasks
- Local desktop notifications in addition to Calendar reminders

## License

[MIT](LICENSE) © 2026 bocho0600
