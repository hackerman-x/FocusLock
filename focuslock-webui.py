#!/usr/bin/env python3
"""FocusLock web UI -- pywebview shell around webui/index.html.

All privileged work still happens the same way it did in the Tkinter
version: focuslock-apply.sh / focuslock-youtube-break-apply.sh, invoked via
`sudo -S -k`, with the password piped over stdin from a field the user
typed in this same local app -- never sent anywhere else. The JS frontend
never touches sudo directly; every privileged call goes through the Api
class below.
"""
import os
import subprocess
import sys
from datetime import datetime, date, timedelta

# Must be set before GTK/GDK initialize (i.e. before `import webview`, which
# imports gi/Gtk at module load time). Without this, GDK creates a native
# Wayland surface under Hyprland, and window-manager float/tile placement
# becomes entirely compositor-side policy with no client-side override --
# Wayland deliberately doesn't expose an X11-style "hint me as floating"
# property. Forcing XWayland here makes this window behave exactly like the
# Tkinter version (which only ever runs via XWayland, since Tk has no native
# Wayland backend at all), where the EWMH window-type hint below is honored.
# This is a real override, not setdefault(): a Wayland session sets
# GDK_BACKEND=wayland in its own environment, so setdefault() would leave
# that in place and silently do nothing.
os.environ["GDK_BACKEND"] = "x11"

import webview

import focuslock_core as core

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI_DIR = os.path.join(SELF_DIR, "webui")


def _activity_payload(weeks=18):
    history = core.load_history()
    locked_days = core.locked_days_from_history(history)
    today = date.today()
    # Snap the END forward to the coming Sunday (not the start backward to
    # Monday) so the range is always exactly weeks*7 days -- snapping the
    # start backward instead can overshoot by a few days depending on
    # today's weekday, producing more cells than the grid has columns for.
    week_end = today + timedelta(days=6 - today.weekday())
    range_start = week_end - timedelta(days=weeks * 7 - 1)

    cells = []
    d = range_start
    while d <= week_end:
        cells.append({"date": d.isoformat(), "locked": d in locked_days and d <= today})
        d += timedelta(days=1)

    locked_count = sum(1 for dd in locked_days if range_start <= dd <= today)
    return {"weeks": weeks, "cells": cells, "locked_count": locked_count}


class Api:
    # ---------- read-only state ----------

    def is_locked(self):
        return core.read_file(core.UNLOCK_AT_FILE) is not None

    def get_state(self):
        unlock_at = core.read_file(core.UNLOCK_AT_FILE)
        if unlock_at:
            blocked_app_keys = core.detect_blocked_apps()
            blocked_domain_keys = core.detect_blocked_domains()
            app_label_map = dict(core.APPS)
            domain_label_map = dict(core.DOMAINS)
            today_str = date.today().isoformat()
            used_today = core.read_file(core.LAST_USED_FILE) == today_str
            return {
                "locked": True,
                "unlock_at": unlock_at,
                "intent": core.read_file(core.INTENT_FILE),
                "blocked_apps": [[k, app_label_map.get(k, k)] for k in blocked_app_keys],
                "blocked_domains": [[k, domain_label_map.get(k, k)] for k in blocked_domain_keys],
                "youtube_available": "youtube" in blocked_domain_keys,
                "youtube_used_today": used_today,
                "youtube_reblock_at": core.read_file(core.UNTIL_FILE) if used_today else None,
            }
        return {
            "locked": False,
            "apps": [list(a) for a in core.APPS],
            "domains": [list(d) for d in core.DOMAINS],
            "stats": core.load_stats(),
            "presets": core.load_presets(),
            "activity": _activity_payload(),
        }

    def seconds_until(self, unlock_at_str):
        try:
            ts = subprocess.check_output(["date", "-d", unlock_at_str, "+%s"], text=True).strip()
            return int(ts) - int(datetime.now().timestamp())
        except Exception:
            return None

    def preview_duration(self, days, hours, minutes):
        offset = f"+{int(days)} days +{int(hours)} hours +{int(minutes)} minutes"
        return {
            "human": core.run_date("+%A, %Y-%m-%d %H:%M:%S %Z", offset=offset),
            "calendar": core.run_date("+%Y-%m-%d %H:%M:%S", offset=offset),
        }

    # ---------- presets ----------

    def save_preset(self, name, apps, domains):
        presets = core.load_presets()
        presets[name] = {"apps": apps, "domains": domains}
        core.save_presets(presets)
        return {"ok": True}

    # ---------- privileged actions ----------

    def start_block(self, days, hours, minutes, apps, domains, intent, password):
        offset = f"+{int(days)} days +{int(hours)} hours +{int(minutes)} minutes"
        unlock_human = core.run_date("+%A, %Y-%m-%d %H:%M:%S %Z", offset=offset)
        unlock_calendar = core.run_date("+%Y-%m-%d %H:%M:%S", offset=offset)

        apply_script = os.path.join(SELF_DIR, "focuslock-apply.sh")
        cmd = [
            "sudo", "-S", "-k", "bash", apply_script,
            unlock_human, unlock_calendar,
            ",".join(apps) or "none",
            ",".join(domains) or "none",
            intent or "",
        ]
        proc = subprocess.run(cmd, input=password + "\n", text=True, capture_output=True)
        if proc.returncode != 0:
            return {"ok": False, "error": proc.stderr or "Unknown error (check sudo password)."}

        end_date = datetime.strptime(unlock_calendar.split()[0], "%Y-%m-%d").date()
        prev_stats = core.load_stats()
        new_stats = core.bump_streak(unlock_calendar)
        core.record_session(date.today(), end_date, apps, domains, intent or "")
        core.check_milestones(prev_stats, new_stats)

        return {"ok": True, "unlock_human": unlock_human}

    def youtube_break(self, password):
        reblock_human = core.run_date("+%A, %Y-%m-%d %H:%M:%S %Z", offset="+1 hour")
        reblock_calendar = core.run_date("+%Y-%m-%d %H:%M:%S", offset="+1 hour")
        apply_script = os.path.join(SELF_DIR, "focuslock-youtube-break-apply.sh")
        cmd = ["sudo", "-S", "-k", "bash", apply_script, reblock_human, reblock_calendar]
        proc = subprocess.run(cmd, input=password + "\n", text=True, capture_output=True)
        if proc.returncode != 0:
            return {"ok": False, "error": proc.stderr or "Unknown error."}
        return {"ok": True, "reblock_human": reblock_human}


if __name__ == "__main__":
    if sys.platform != "linux":
        print("This tool is Linux-only.", file=sys.stderr)
        sys.exit(1)

    api = Api()
    window = webview.create_window(
        "FocusLock",
        url=os.path.join(WEBUI_DIR, "index.html"),
        js_api=api,
        width=860,
        height=1000,
        min_size=(640, 700),
        background_color="#0b0616",
    )

    def _hint_floating():
        """Ask the window manager to float this window instead of tiling
        it, via the standard EWMH _NET_WM_WINDOW_TYPE hint -- same fix as
        the Tkinter version needed, done here through GTK's own API since
        pywebview's GTK backend is a native Gtk.Window, not a Tk one.
        Fired on before_show, after the native window exists but before
        it's mapped, since tiling WMs place windows once at map time."""
        try:
            import gi
            gi.require_version("Gdk", "3.0")
            from gi.repository import Gdk
            window.native.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        except Exception:
            pass

    window.events.before_show += _hint_floating
    # Private mode (pywebview's default) leaves WebKitGTK without
    # localStorage, so the light/dark choice would never be remembered.
    webview.start(gui="gtk", private_mode=False,
                  storage_path=os.path.join(core.CONFIG_DIR, "webview"))
