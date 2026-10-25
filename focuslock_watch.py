"""Notices blocked-app attempts by watching for FocusLock's own "X is
blocked" desktop notifications on the session bus.

The blocking wrappers made by focuslock-apply.sh log each attempt to the
distraction log themselves -- but only wrappers made by an up-to-date
apply script do. A lock started before that (its wrappers are root-owned and
stay as they are until it ends) only shows the notification. While the GUI is
open, this fills that gap: every wrapper, old or new, sends a notification
titled "FocusLock", so watching for those catches every attempt.

Uses dbus-monitor with a match rule on the notification title (arg3), so
the bus only ever hands over FocusLock's notifications -- never other apps'.
Runs on a background thread; nothing here touches Tk. Events are queued
for the GUI to collect -- or run on its own (see the bottom of this file).
"""
import os
import queue
import re
import shutil
import subprocess
import threading
import time

MATCH = ("type='method_call',interface='org.freedesktop.Notifications',member='Notify',"
         "arg3='FocusLock'")
BODY_RE = re.compile(r"^FocusLock: (.+?) is blocked until ")
STRING_RE = re.compile(r'^\s+string "(.*)"\s*$')


def wrapper_name(name):
    """The name as focuslock-apply.sh writes it into a wrapper (see its
    `tr -cd 'A-Za-z0-9 ._()+-' | cut -c1-40`), for matching custom apps."""
    return re.sub(r"[^A-Za-z0-9 ._()+-]", "", name)[:40]


class NotificationWatcher:
    def __init__(self):
        self.events = queue.Queue()   # (epoch, app name from the message)
        self.proc = None
        self._thread = None

    def start(self):
        exe = shutil.which("dbus-monitor")
        if not exe or self.proc is not None:
            return False
        try:
            self.proc = subprocess.Popen([exe, "--session", MATCH], stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True, errors="replace")
        except OSError:
            self.proc = None
            return False
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        return True

    def _read(self):
        strings = None
        for line in self.proc.stdout:
            if line.startswith(("method call", "signal", "method return", "error")):
                strings = [] if "member=Notify" in line else None
                continue
            if strings is None:
                continue
            m = STRING_RE.match(line)
            if not m:
                continue
            strings.append(m.group(1))
            # Notify(app_name, replaces_id, app_icon, summary, body, ...): the
            # 4th string is the body.
            if len(strings) == 4:
                if strings[2] == "FocusLock":
                    hit = BODY_RE.match(strings[3])
                    if hit:
                        self.events.put((int(time.time()), hit.group(1)))
                strings = None

    def drain(self):
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
            self.proc = None


# ---------- standalone logger ----------
# FocusLock starts this as its own process (or systemd --user does, if "Start
# with your computer" is on), so attempts keep being logged while the app is
# closed. One copy at a time; it exits when the lock ends or the session does.

def _single_instance(path):
    import fcntl
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd   # held until exit


def lock_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "focuslock")
    return os.path.join(base, "focuslock-attempt-logger.lock")


def run(lock_file=None, check_every=30.0):
    """Log FocusLock 'X is blocked' notifications until the lock ends. Returns an exit code."""
    import focuslock_core as core
    lock_file = lock_file or core.UNLOCK_AT_FILE
    if not os.path.exists(lock_file):
        return 0
    held = _single_instance(lock_path())
    if held is None:
        return 0                      # already running
    watcher = NotificationWatcher()
    if not watcher.start():
        return 1
    names, names_at, checked = {}, 0.0, time.monotonic()
    try:
        while watcher.proc.poll() is None:            # dbus-monitor ends with the session
            time.sleep(1)
            if time.monotonic() - names_at > 60:      # pick up apps added since
                names = {wrapper_name(n): k for k, n in core.all_apps()}
                names_at = time.monotonic()
            for ts, name in watcher.drain():
                key = names.get(name)
                if key:                               # "This app" (the hidden block) is never logged
                    core.log_attempt(key, ts)
            if time.monotonic() - checked > check_every:
                checked = time.monotonic()
                if not os.path.exists(lock_file):
                    return 0
        return 0
    finally:
        watcher.stop()


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    ap = argparse.ArgumentParser(description="FocusLock: log blocked-app attempts while the app is closed.")
    ap.add_argument("--lock-file", help="(tests) the lock's unlock_at file")
    ap.add_argument("--check-every", type=float, default=30.0)
    a = ap.parse_args()
    sys.exit(run(a.lock_file, a.check_every))
