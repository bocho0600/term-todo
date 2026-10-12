"""System-tray icon (StatusNotifierItem) showing pending tasks.

Talks D-Bus directly through PyGObject's Gio, so it needs no AppIndicator
library — just ``python3-gi`` (preinstalled on Ubuntu) and a desktop that
hosts StatusNotifier icons (GNOME with the Ubuntu AppIndicator extension, KDE,
XFCE, ...).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from gi.repository import GLib

from . import storage
from .dates import format_due, is_overdue
from .models import Task

SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
APP_BUS_NAME = "dev.termtodo.Tray"
MAX_TASKS_SHOWN = 15
REFRESH_SECONDS = 30

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg type="s"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
      <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" direction="in"/><arg type="as" direction="in"/>
      <arg type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/>
    </method>
    <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
    <method name="AboutToShowGroup">
      <arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ia{sv}as)"/></signal>
    <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
    <signal name="ItemActivationRequested"><arg type="i"/><arg type="u"/></signal>
  </interface>
</node>
"""

# 3x5 pixel font for the count shown inside the icon.
_DIGITS = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "+": ["000", "010", "111", "010", "000"],
}
_TICK = [
    "000000001",
    "000000011",
    "100000110",
    "110001100",
    "011011000",
    "001110000",
    "000100000",
]
SIZE = 22


def render_icon(count: int) -> bytes:
    """ARGB32 (network byte order) pixmap: a rounded box with the count inside,
    or a tick when nothing is pending."""
    px = [[0] * SIZE for _ in range(SIZE)]  # 0 = transparent, 1 = ink

    lo, hi = 1, SIZE - 2
    for y in range(lo, hi + 1):
        for x in range(lo, hi + 1):
            on_edge = x in (lo, hi) or y in (lo, hi)
            corner = x in (lo, hi) and y in (lo, hi)
            if on_edge and not corner:
                px[y][x] = 1
            # thicken the border for legibility on small panels
            if x in (lo + 1, hi - 1) or y in (lo + 1, hi - 1):
                if lo + 1 <= x <= hi - 1 and lo + 1 <= y <= hi - 1:
                    px[y][x] = 1

    def blit(rows: List[str], ox: int, oy: int, scale: int, clear: bool = True) -> None:
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                if ch != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px[oy + ry * scale + dy][ox + rx * scale + dx] = 1

    # clear the interior so only a border box remains, then draw content
    for y in range(lo + 3, hi - 2):
        for x in range(lo + 3, hi - 2):
            px[y][x] = 0

    if count <= 0:
        w = len(_TICK[0])
        blit(_TICK, (SIZE - w * 2) // 2, (SIZE - len(_TICK) * 2) // 2, 2)
    else:
        text = str(count) if count < 100 else "99+"
        scale = 3 if len(text) == 1 else 2 if len(text) == 2 else 1
        glyph_w = 3 * scale
        total_w = len(text) * glyph_w + (len(text) - 1) * scale
        ox = (SIZE - total_w) // 2
        oy = (SIZE - 5 * scale) // 2
        for ch in text:
            blit(_DIGITS[ch], ox, oy, scale)
            ox += glyph_w + scale

    out = bytearray()
    for row in px:
        for v in row:
            out += b"\xff\xff\xff\xff" if v else b"\x00\x00\x00\x00"
    return bytes(out)


def _find_terminal_cmd() -> Optional[List[str]]:
    exe = shutil.which("term-todo") or str(Path(sys.argv[0]).resolve())
    for term, flag in (
        ("gnome-terminal", "--"),
        ("kgx", "-e"),
        ("konsole", "-e"),
        ("xfce4-terminal", "-x"),
        ("x-terminal-emulator", "-e"),
        ("xterm", "-e"),
    ):
        path = shutil.which(term)
        if path:
            return [path, flag, exe, "ui"]
    return None


def _esc(label: str) -> str:
    return label.replace("_", "__")


def _task_label(t: Task, now: datetime) -> str:
    title = t.title if len(t.title) <= 48 else t.title[:47] + "…"
    label = f"○  {title}"
    if t.due:
        label += f"   ·  {'⚠ ' if is_overdue(t.due, now) else ''}{format_due(t.due)}"
    if t.notes:
        label += "  ✎"
    return label


class Tray:
    def __init__(self) -> None:
        from gi.repository import Gio, GLib  # noqa: PLC0415 - optional dependency

        self.Gio, self.GLib = Gio, GLib
        self.loop = GLib.MainLoop()
        self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.revision = 1
        self.menu_items: List[Tuple[int, Dict[str, "GLib.Variant"]]] = []
        self.actions: Dict[int, Callable[[], None]] = {}
        self.count = -1
        self._snapshot: Tuple = ()
        self.pixmap = b""
        self._rebuild(force=True)

    # ---- model -> menu ----
    def _rebuild(self, force: bool = False) -> bool:
        GLib = self.GLib
        tasks = storage.list_tasks()
        now = datetime.now()
        snapshot = tuple((t.id, t.title, t.due, t.bucket, bool(t.notes)) for t in tasks)
        if snapshot == self._snapshot and not force:
            return False
        self._snapshot = snapshot
        self.count = len(tasks)
        self.pixmap = render_icon(self.count)

        items: List[Tuple[int, Dict[str, GLib.Variant]]] = []
        self.actions = {}
        next_id = [1]

        def add(props: Dict[str, object], action: Optional[Callable[[], None]] = None) -> None:
            vprops = {
                k: GLib.Variant("b" if isinstance(v, bool) else "s", v) for k, v in props.items()
            }
            items.append((next_id[0], vprops))
            if action:
                self.actions[next_id[0]] = action
            next_id[0] += 1

        overdue = sum(1 for t in tasks if t.due and is_overdue(t.due, now))
        head = f"term-todo — {self.count} pending" + (f", {overdue} overdue" if overdue else "")
        add({"label": _esc(head), "enabled": False})
        add({"type": "separator"})

        if not tasks:
            add({"label": "Nothing to do 🎉", "enabled": False})
        shown = 0
        current_bucket = None
        for t in tasks:
            if shown >= MAX_TASKS_SHOWN:
                add({"label": _esc(f"…and {len(tasks) - shown} more"), "enabled": False})
                break
            if t.bucket != current_bucket:
                current_bucket = t.bucket
                add({"label": _esc(f"◆ {t.bucket}"), "enabled": False})
            add({"label": _esc(_task_label(t, now)), "enabled": True})
            shown += 1

        add({"type": "separator"})
        add({"label": "Open term-todo", "enabled": True}, self._open_ui)
        add({"label": "Quit tray icon", "enabled": True}, self.loop.quit)
        self.menu_items = items
        return True

    def _open_ui(self) -> None:
        cmd = _find_terminal_cmd()
        if cmd:
            subprocess.Popen(cmd, start_new_session=True)

    # ---- D-Bus: StatusNotifierItem ----
    def _sni_prop(self, _c, _s, _p, _i, name):
        V = self.GLib.Variant
        tip_title = "term-todo"
        tip_body = f"{self.count} task{'s' if self.count != 1 else ''} pending"
        table = {
            "Category": V("s", "ApplicationStatus"),
            "Id": V("s", "term-todo"),
            "Title": V("s", "term-todo"),
            "Status": V("s", "Active"),
            "WindowId": V("u", 0),
            "IconName": V("s", ""),
            "IconPixmap": V("a(iiay)", [(SIZE, SIZE, self.pixmap)]),
            "OverlayIconName": V("s", ""),
            "OverlayIconPixmap": V("a(iiay)", []),
            "AttentionIconName": V("s", ""),
            "AttentionIconPixmap": V("a(iiay)", []),
            "AttentionMovieName": V("s", ""),
            "ToolTip": V("(sa(iiay)ss)", ("", [], tip_title, tip_body)),
            "ItemIsMenu": V("b", True),
            "Menu": V("o", MENU_PATH),
        }
        return table.get(name)

    def _sni_method(self, _c, _s, _p, _i, method, _params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            self._open_ui() if method == "SecondaryActivate" else None
        invocation.return_value(None)

    # ---- D-Bus: dbusmenu ----
    def _child_variant(self, item_id: int, props) -> "GLib.Variant":
        V = self.GLib.Variant
        return V("(ia{sv}av)", (item_id, props, []))

    def _menu_prop(self, _c, _s, _p, _i, name):
        V = self.GLib.Variant
        return {
            "Version": V("u", 3),
            "TextDirection": V("s", "ltr"),
            "Status": V("s", "normal"),
            "IconThemePath": V("as", []),
        }.get(name)

    def _menu_method(self, _c, _s, _p, _i, method, params, invocation):
        V = self.GLib.Variant
        if method == "GetLayout":
            parent = params.unpack()[0]
            if parent == 0:
                children = [self._child_variant(i, p) for i, p in self.menu_items]
                root = (0, {"children-display": V("s", "submenu")}, children)
            else:
                match = [(i, p) for i, p in self.menu_items if i == parent]
                root = (parent, match[0][1] if match else {}, [])
            invocation.return_value(V("(u(ia{sv}av))", (self.revision, root)))
        elif method == "GetGroupProperties":
            ids = params.unpack()[0]
            out = [(i, p) for i, p in self.menu_items if not ids or i in ids]
            invocation.return_value(V("(a(ia{sv}))", (out,)))
        elif method == "GetProperty":
            item_id, prop = params.unpack()
            val = dict(self.menu_items).get(item_id, {}).get(prop)
            invocation.return_value(V("(v)", (val if val is not None else V("s", ""),)))
        elif method == "Event":
            item_id, event, _data, _ts = params.unpack()
            if event == "clicked" and item_id in self.actions:
                self.GLib.idle_add(self.actions[item_id])
            invocation.return_value(None)
        elif method == "EventGroup":
            for item_id, event, _d, _t in params.unpack()[0]:
                if event == "clicked" and item_id in self.actions:
                    self.GLib.idle_add(self.actions[item_id])
            invocation.return_value(V("(ai)", ([],)))
        elif method == "AboutToShow":
            changed = self._rebuild()
            if changed:
                self.revision += 1
            invocation.return_value(V("(b)", (changed,)))
        elif method == "AboutToShowGroup":
            self._rebuild()
            invocation.return_value(V("(aiai)", ([], [])))
        else:
            invocation.return_value(None)

    # ---- lifecycle ----
    def _emit(self, path: str, iface: str, signal: str, params=None) -> None:
        self.conn.emit_signal(None, path, iface, signal, params)

    def _tick(self) -> bool:
        if self._rebuild():
            self.revision += 1
            V = self.GLib.Variant
            self._emit(SNI_PATH, "org.kde.StatusNotifierItem", "NewIcon")
            self._emit(SNI_PATH, "org.kde.StatusNotifierItem", "NewToolTip")
            self._emit(MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated",
                       V("(ui)", (self.revision, 0)))
        return True

    def _register_with_watcher(self, *_args) -> None:
        V = self.GLib.Variant
        try:
            self.conn.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                V("(s)", (self.item_name,)),
                None, self.Gio.DBusCallFlags.NONE, -1, None,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"term-todo tray: could not register with panel: {exc}", file=sys.stderr)

    def run(self) -> int:
        Gio, GLib = self.Gio, self.GLib

        # single instance
        reply = self.conn.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "RequestName", GLib.Variant("(su)", (APP_BUS_NAME, 4)),  # DO_NOT_QUEUE
            None, Gio.DBusCallFlags.NONE, -1, None,
        )
        if reply.unpack()[0] != 1:
            print("term-todo tray is already running.", file=sys.stderr)
            return 1

        self.item_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.conn.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "RequestName", GLib.Variant("(su)", (self.item_name, 0)),
            None, Gio.DBusCallFlags.NONE, -1, None,
        )
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.conn.register_object(SNI_PATH, sni, self._sni_method, self._sni_prop, None)
        self.conn.register_object(MENU_PATH, menu, self._menu_method, self._menu_prop, None)

        # (re-)register whenever the panel's watcher appears, e.g. at login
        Gio.bus_watch_name_on_connection(
            self.conn, "org.kde.StatusNotifierWatcher", Gio.BusNameWatcherFlags.NONE,
            self._register_with_watcher, None,
        )
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        return 0


AUTOSTART_FILE = Path(
    os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
) / "autostart" / "term-todo-tray.desktop"


def install_autostart() -> Path:
    exe = shutil.which("term-todo") or str(Path(sys.argv[0]).resolve())
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=term-todo tray\n"
        "Comment=Shows pending term-todo tasks in the panel\n"
        f"Exec={exe} tray\n"
        "X-GNOME-Autostart-enabled=true\n"
        "NoDisplay=true\n"
    )
    return AUTOSTART_FILE


def remove_autostart() -> bool:
    if AUTOSTART_FILE.exists():
        AUTOSTART_FILE.unlink()
        return True
    return False


def run() -> int:
    try:
        tray = Tray()
    except ImportError:
        print(
            "The tray icon needs PyGObject (python3-gi), which isn't visible to this install.\n"
            "On Ubuntu: sudo apt install python3-gi, then recreate the venv with "
            "--system-site-packages.",
            file=sys.stderr,
        )
        return 1
    return tray.run()


def spawn_detached() -> None:
    exe = shutil.which("term-todo") or str(Path(sys.argv[0]).resolve())
    subprocess.Popen(
        [exe, "tray"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
