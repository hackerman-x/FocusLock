#!/usr/bin/env python3
"""FocusLock's shared, UI-agnostic business logic -- config, state files,
stats/streak/preset/history persistence, and the app/domain block lists.

Used by both focuslock-gui.py (Tkinter) and focuslock-webui.py (pywebview).
Nothing in this file imports a GUI toolkit.
"""
import json
import os
import bisect
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, date, timedelta

import focuslock_platform as plat

SELF_DIR = os.path.dirname(os.path.abspath(__file__))

# Set by the AppImage runtime to the real path of the .AppImage file. When
# running from one, SELF_DIR is a temporary FUSE mount that root can't read
# and that vanishes when the app closes, so helpers and services can't point
# into it (see privileged_script and watcher_command).
APPIMAGE = os.environ.get("APPIMAGE")

# Scripts run as root, plus the files they install into /usr/local/sbin.
PRIVILEGED_FILES = ("focuslock-apply.sh", "focuslock-unlock.sh", "focuslock-sitelog.py",
                    "focuslock-youtube-break-apply.sh", "focuslock-youtube-reblock.sh")


def privileged_script(name):
    """Path to a helper script that sudo can run. From an AppImage, the
    helpers are first copied to a private folder outside the mount."""
    if not APPIMAGE:
        return os.path.join(SELF_DIR, name)
    dest = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir(), "focuslock-helpers")
    os.makedirs(dest, mode=0o700, exist_ok=True)
    for f in PRIVILEGED_FILES:
        shutil.copy2(os.path.join(SELF_DIR, f), os.path.join(dest, f))
    return os.path.join(dest, name)


def watcher_command():
    """Command that starts the background attempt logger (focuslock_watch.py)."""
    if APPIMAGE:
        return [APPIMAGE, "--watch"]
    return [sys.executable, os.path.join(SELF_DIR, "focuslock_watch.py")]

LOCKDIR = plat.LOCKDIR
UNLOCK_AT_FILE = os.path.join(LOCKDIR, "unlock_at")
LOCKED_AT_FILE = os.path.join(LOCKDIR, "locked_at")
SELECTED_APPS_FILE = os.path.join(LOCKDIR, "selected_apps")
LAST_USED_FILE = os.path.join(LOCKDIR, "youtube_break_last_used")
UNTIL_FILE = os.path.join(LOCKDIR, "youtube_break_until")
INTENT_FILE = os.path.join(LOCKDIR, "intent")
HOSTS_FILE = plat.HOSTS_FILE
SITELOG_ADDR = "127.83.76.1"                                  # see focuslock-sitelog.py
SITELOG_FILE = plat.SITELOG_FILE     # written by it, readable by everyone (Linux only)

CONFIG_DIR = plat.CONFIG_DIR
STATS_FILE = os.path.join(CONFIG_DIR, "stats.json")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")
BADGES_FILE = os.path.join(CONFIG_DIR, "badges.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
POMO_PLAN_FILE = os.path.join(CONFIG_DIR, "pomodoro_plan.json")
CUSTOM_APPS_FILE = os.path.join(CONFIG_DIR, "custom_apps.json")
CUSTOM_SITES_FILE = os.path.join(CONFIG_DIR, "custom_sites.json")
POMO_HISTORY_FILE = os.path.join(CONFIG_DIR, "pomodoro_history.json")
GOALS_FILE = os.path.join(CONFIG_DIR, "goals.json")
TASKS_FILE = os.path.join(CONFIG_DIR, "tasks.json")
TEMPLATES_FILE = os.path.join(CONFIG_DIR, "templates.json")

MILESTONE_STREAKS = {3, 7, 14, 21, 30, 60, 100, 200, 365}
MILESTONE_SESSIONS = {5, 10, 25, 50, 100, 250}

# Must match the keys (and paths/domains) in focuslock-apply.sh's
# APP_DEFS / DOMAIN_DEFS. Anything apply.sh blocks unconditionally (its
# ALWAYS_BLOCKED_FLATPAKS) is intentionally absent here so it never shows.
APPS = [
    ("discord", "Discord"),
    ("minecraft", "Minecraft Launcher"),
    ("modrinth", "Modrinth App"),
    ("steam", "Steam"),
    ("stardew", "Stardew Valley (SMAPI)"),
    ("xonotic", "Xonotic"),
    ("nexuiz", "Nexuiz"),
    ("openspades", "OpenSpades"),
    ("oneclient", "OneClient"),
    ("flatpak", "Flatpak"),
    ("godot", "Godot"),
    ("unityhub", "Unity Hub"),
    ("aseprite", "Aseprite"),
]

# Windows: the same keys where the app exists there (so presets and stats
# mean the same thing), blocked by program file name -- see focuslock_win.
# Names with a * only work for the guard task, which matches running
# programs; the launch-time block needs an exact name.
WIN_APP_EXES = {
    "discord": ["Discord.exe"],
    "minecraft": ["MinecraftLauncher.exe", "Minecraft.exe", "Minecraft.Windows.exe"],
    "modrinth": ["Modrinth App.exe"],
    "steam": ["steam.exe"],
    "roblox_player": ["RobloxPlayerBeta.exe", "RobloxPlayerLauncher.exe"],
    "stardew": ["Stardew Valley.exe", "StardewModdingAPI.exe"],
    "godot": ["Godot*.exe"],
    "unityhub": ["Unity Hub.exe", "Unity.exe"],
    "aseprite": ["Aseprite.exe"],
}
if plat.IS_WINDOWS:
    APPS = [
        ("discord", "Discord"),
        ("minecraft", "Minecraft Launcher"),
        ("modrinth", "Modrinth App"),
        ("steam", "Steam"),
        ("roblox_player", "Roblox"),
        ("stardew", "Stardew Valley (SMAPI)"),
        ("godot", "Godot"),
        ("unityhub", "Unity Hub"),
        ("aseprite", "Aseprite"),
    ]

# Shown in their own group and left unticked by default: these are the
# tools for game-dev work, so blocking them should be a deliberate choice.
DEV_TOOLS = {"godot", "unityhub", "aseprite"}
DOMAINS = [
    ("discord_web", "Discord (web)"),
    ("crazygames", "CrazyGames"),
    ("gxgames", "GX Games"),
    ("poki", "Poki"),
    ("roblox", "Roblox (web)"),
    ("instagram", "Instagram (web)"),
    ("youtube", "YouTube"),
]

# Only used to read what a lock from before the selected_apps manifest
# existed had blocked; newer locks are read from that manifest instead.
LEGACY_APP_PATHS = {
    "discord": "/usr/bin/discord",
    "minecraft": "/usr/bin/minecraft-launcher",
    "steam": "/usr/bin/steam",
    "flatpak": "/usr/bin/flatpak",
    "oneclient": "/home/shahid/OneClient/oneclient_app_2.3.1_x86_64.AppImage",
}
DOMAIN_GROUPS = {
    "discord_web": ["discord.com", "www.discord.com", "discordapp.com"],
    "crazygames": ["crazygames.com", "www.crazygames.com"],
    "gxgames": ["gx.games", "www.gx.games"],
    "poki": ["poki.com", "www.poki.com"],
    "roblox": ["roblox.com", "www.roblox.com", "web.roblox.com"],
    "instagram": ["instagram.com", "www.instagram.com"],
    "youtube": ["youtube.com", "www.youtube.com", "m.youtube.com"],
}


def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


_OFFSET_PART = re.compile(r"([+-]?\d+)\s*(day|hour|minute|second)s?\b")
_OFFSET_UNITS = {"day": 86400, "hour": 3600, "minute": 60, "second": 1}


def offset_seconds(offset):
    """'+2 days +3 hours +0 minutes' -> seconds. Only the forms FocusLock
    itself builds are understood (it used to pass these to GNU date)."""
    return sum(int(n) * _OFFSET_UNITS[unit] for n, unit in _OFFSET_PART.findall(offset or ""))


def run_date(fmt, offset=None):
    """Local time now (plus offset), formatted like `date -d offset fmt`."""
    when = datetime.fromtimestamp(time.time() + offset_seconds(offset)).astimezone()
    return when.strftime(fmt.lstrip("+")).strip()


_STAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def parse_unlock_time(text):
    """Epoch for an unlock time as the lock writes it
    ('Tuesday, 2026-10-20 23:00:00 IST'), read as local time; None if unreadable."""
    m = _STAMP.search(text or "")
    if not m:
        return None
    try:
        return int(datetime.strptime(m.group(0), "%Y-%m-%d %H:%M:%S").timestamp())
    except (ValueError, OverflowError):
        return None


def detect_blocked_apps():
    """Keys of the apps the active lock blocked, in APPS order.

    apply.sh only lists an app in selected_apps if it actually blocked
    something for it, and never lists its hidden always-on blocks -- so this
    must come from that manifest, not from scanning for .focuslock-real
    files (the hidden block wraps /usr/bin/flatpak on every lock, which a
    disk scan would wrongly report as "Flatpak blocked")."""
    manifest = read_file(SELECTED_APPS_FILE)
    if manifest is not None:
        keys = manifest.split()
        known = [key for key, _ in all_apps() if key in keys]
        # A custom app removed from the Apps tab mid-lock is still blocked
        # until unlock, so still list it (by key).
        return known + [k for k in keys if k.startswith("c_") and k not in known]
    return [key for key, path in LEGACY_APP_PATHS.items() if os.path.exists(path + ".focuslock-real")]


def lock_progress():
    """(started_epoch, ends_epoch) for the active lock, or None if unknown
    (no lock, or one started before locked_at was recorded)."""
    started = read_file(LOCKED_AT_FILE)
    ends_human = read_file(UNLOCK_AT_FILE)
    if not started or not ends_human:
        return None
    ends = parse_unlock_time(ends_human)
    if ends is None or not started.isdigit():
        return None
    return int(started), ends


def domain_groups():
    """Built-in plus custom site groups: {key: [domains]}."""
    groups = dict(DOMAIN_GROUPS)
    for site in load_custom_sites():
        groups[site["key"]] = list(site["domains"])
    return groups


def detect_blocked_domains():
    hosts = read_file(HOSTS_FILE) or ""
    blocked = []
    for key, domains in domain_groups().items():
        # 0.0.0.0 in locks started before the site logger; its address since.
        if any(f"0.0.0.0 {d}" in hosts or f"{SITELOG_ADDR} {d}" in hosts for d in domains):
            blocked.append(key)
    return blocked


# ---------- persistent stats / presets / history (user-owned, survive lock cycles) ----------

def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_stats():
    _ensure_config_dir()
    try:
        with open(STATS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"streak": 0, "longest_streak": 0, "total_sessions": 0, "last_unlock_date": None}


def save_stats(stats):
    _ensure_config_dir()
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def bump_streak(unlock_calendar_str, today=None):
    """Call once, right when a new lock is successfully engaged.

    Streak counts consecutive calendar days on which a lock was started (at
    most a 1-day gap since the previous one ended). Capped at one increment
    per real calendar day, so starting several short locks in the same day
    (durations can be minutes/hours, not just days) can't inflate the streak
    -- each still counts toward total_sessions, just not streak.
    """
    today = today or date.today()
    today_str = today.isoformat()
    stats = load_stats()
    end_date = datetime.strptime(unlock_calendar_str.split()[0], "%Y-%m-%d").date()

    if stats.get("last_start_date") == today_str:
        stats["total_sessions"] = stats.get("total_sessions", 0) + 1
        stats["last_unlock_date"] = end_date.isoformat()
        save_stats(stats)
        return stats

    last = stats.get("last_unlock_date")
    if last is None:
        streak = 1
    else:
        last_date = datetime.strptime(last, "%Y-%m-%d").date()
        gap = (today - last_date).days
        streak = stats.get("streak", 0) + 1 if gap <= 1 else 1

    stats["streak"] = streak
    stats["longest_streak"] = max(stats.get("longest_streak", 0), streak)
    stats["total_sessions"] = stats.get("total_sessions", 0) + 1
    stats["last_unlock_date"] = end_date.isoformat()
    stats["last_start_date"] = today_str
    save_stats(stats)
    return stats


def load_presets():
    _ensure_config_dir()
    try:
        with open(PRESETS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_presets(presets):
    _ensure_config_dir()
    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=2)


def load_history():
    _ensure_config_dir()
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(history):
    _ensure_config_dir()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_session(start_date, end_date, apps, domains, intent, started_at=None, ends_at=None):
    """Call once, right when a new lock is successfully engaged.

    started_at/ends_at are epoch seconds. Sessions recorded before these
    existed only have dates, so stats treat their duration as unknown."""
    history = load_history()
    entry = {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "apps": apps,
        "domains": domains,
        "intent": intent,
    }
    if started_at is not None and ends_at is not None:
        entry["started_at"] = int(started_at)
        entry["ends_at"] = int(ends_at)
    history.append(entry)
    save_history(history)
    return history


def session_bounds(session):
    """(started_epoch, ends_epoch) if the session recorded them, else None."""
    a, b = session.get("started_at"), session.get("ends_at")
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b > a:
        return a, b
    return None


STATS_WEEKS = 8


def compute_stats(history, now=None):
    """Everything the Stats page shows, derived from history alone.

    Focus time only counts sessions with recorded start/end times; an
    in-progress session counts up to now, not to its scheduled end."""
    now = time.time() if now is None else now
    today = date.fromtimestamp(now)
    this_monday = today - timedelta(days=today.weekday())
    weeks = STATS_WEEKS
    by_weekday = [0] * 7
    weekly_sessions = [0] * weeks          # oldest week first
    weekly_seconds = [0] * weeks
    blocked = Counter()
    focus = longest = timed = 0
    valid = []
    for s in history:
        try:
            start = date.fromisoformat(s["start"])
        except (KeyError, TypeError, ValueError):
            continue
        valid.append(s)
        by_weekday[start.weekday()] += 1
        secs = 0
        bounds = session_bounds(s)
        if bounds:
            a, b = bounds
            secs = max(0, min(b, now) - a)
            focus += secs
            longest = max(longest, b - a)
            timed += 1
        weeks_ago = (this_monday - (start - timedelta(days=start.weekday()))).days // 7
        if 0 <= weeks_ago < weeks:
            weekly_sessions[weeks - 1 - weeks_ago] += 1
            weekly_seconds[weeks - 1 - weeks_ago] += secs
        for key in list(s.get("apps", [])) + list(s.get("domains", [])):
            blocked[key] += 1
    return {
        "sessions": len(valid),
        "timed_sessions": timed,
        "focus_seconds": focus,
        "longest_seconds": longest,
        "by_weekday": by_weekday,
        "weekly_sessions": weekly_sessions,
        "weekly_seconds": weekly_seconds,
        "week_starts": [this_monday - timedelta(weeks=weeks - 1 - i) for i in range(weeks)],
        "top_blocked": blocked.most_common(6),
        "recent": list(reversed(valid[-8:])),
    }


def locked_days_from_history(history):
    """Every calendar day covered by any session, as a set of date objects."""
    days = set()
    for session in history:
        start = datetime.strptime(session["start"], "%Y-%m-%d").date()
        end = datetime.strptime(session["end"], "%Y-%m-%d").date()
        d = start
        while d <= end:
            days.add(d)
            d += timedelta(days=1)
    return days


def _load_json(path, default):
    _ensure_config_dir()
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    _ensure_config_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_settings():
    return _load_json(SETTINGS_FILE, {})


def save_settings(settings):
    _save_json(SETTINGS_FILE, settings)


# ---------- custom apps ----------
# Apps the user adds themselves. focuslock-apply.sh re-checks every one of
# these rules as root before touching anything; the checks here just give
# the GUI early, friendly errors. Keep the two in sync.

# Blocked by apply.sh on every lock and never listed anywhere -- so also
# kept out of the Add App pickers.
HIDDEN_FLATPAKS = {"org.vinegarhq.Sober"}

CUSTOM_KINDS = [("game", "Game"), ("dev", "Dev tool"), ("other", "Other")]

# Programs that must never be wrapped: blocking any of these could lock
# you out of sudo or your desktop, or break the unlock script itself (which
# needs e.g. mv, sed and systemctl to lift the lock).
PROTECTED_NAMES = {
    "sudo", "su", "sudoedit", "pkexec", "doas", "visudo", "passwd", "login",
    "bash", "sh", "dash", "zsh", "fish", "ksh", "env", "python", "python3", "perl", "ruby",
    "systemctl", "systemd", "journalctl", "loginctl", "busctl", "dbus-daemon", "dbus-launch",
    "hyprland", "hyprctl", "hyprpm", "xwayland", "xorg", "x",
    "flatpak", "snap", "snapd", "dpkg", "dpkg-query", "apt", "apt-get",
    "mv", "cp", "rm", "ln", "install", "sed", "awk", "gawk", "mawk", "grep", "cat", "sort", "cut",
    "tr", "date", "logger", "notify-send", "resolvectl", "getent", "chmod", "chown", "tee",
    "head", "tail", "find", "xargs", "stat", "realpath", "readlink", "mkdir", "touch",
    "nano", "vim", "vi", "pw-play", "paplay", "aplay", "pipewire", "wireplumber", "pulseaudio",
    "rofi", "waybar", "kitty", "foot", "alacritty", "wezterm", "gnome-terminal", "konsole", "xterm",
    "i3", "i3bar", "i3status", "i3lock", "sway", "swaybar", "swaylock", "dunst", "mako", "nm-applet",
    "blueman-applet", "flameshot", "kded5", "kded6", "plasmashell", "kwin_wayland", "kwin_x11",
    "kitten", "picom", "compton", "xss-lock", "xautolock", "update-notifier",
}
PROTECTED_PREFIXES = ("python3", "systemd-", "hypr", "ibus", "xdg-", "at-spi", "gvfs", "polkit",
                      "dbus", "fcitx", "pipewire", "wireplumber", "gnome-keyring", "gnome-session",
                      "gnome-shell", "swww", "zeitgeist")
# Background helpers aren't useful to block and are risky to; keep them out
# of the "running now" picker.
_BACKGROUND_HINTS = ("daemon", "notifier", "helper", "agent", "applet", "-lock", "portal", "tray")
# Executables the built-in app list already covers.
BUILTIN_NAMES = {"discord", "minecraft-launcher", "modrinthapp", "steam", "godot3", "nexuiz",
                 "darkplaces", "unityhub", "unityhub-bin", "stardewmoddingapi", "stardewvalley"}
ALLOWED_DIRS = ("/usr/bin/", "/usr/games/", "/usr/local/bin/", "/opt/")
_UNSAFE_PATH_CHARS = re.compile(r"[\x00-\x1f*?\[\]|]")
_FLATPAK_ID = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$")


def load_custom_apps():
    return [a for a in _load_json(CUSTOM_APPS_FILE, []) if isinstance(a, dict) and "key" in a]


def save_custom_apps(apps):
    _save_json(CUSTOM_APPS_FILE, apps)


def sanitize_app_name(name):
    """Names end up inside generated shell scripts, so only plain characters."""
    return re.sub(r"[^A-Za-z0-9 ._()+-]", "", name).strip()[:40]


def make_custom_key(name, existing_keys):
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30] or "app"
    key, n = f"c_{slug}", 2
    while key in existing_keys:
        key, n = f"c_{slug}_{n}", n + 1
    return key


def _pacman_core_pkgs():
    """Names of the packages in Arch's [core] repo -- the pacman stand-in for
    dpkg's required/important/standard priorities."""
    out = subprocess.run(["pacman", "-Slq", "core"], capture_output=True, text=True, timeout=30).stdout
    return set(out.split())


def _pacman_core_paths(paths):
    """The subset of paths owned by a package from [core] (pacman systems)."""
    try:
        out = subprocess.run(["pacman", "-Qo", *paths], capture_output=True, text=True, timeout=60).stdout
        core = _pacman_core_pkgs()
    except (OSError, subprocess.SubprocessError):
        return set()
    found = set()
    for line in out.splitlines():
        # "/usr/bin/ls is owned by coreutils 9.5-1"
        path, sep, rest = line.rpartition(" is owned by ")
        if sep and rest.split()[0] in core:
            found.add(path)
    return found


def _core_package(path):
    """True if a dpkg package owning path is a core system package
    (Priority required/important/standard), or on Arch a [core] package."""
    if not shutil.which("dpkg") and shutil.which("pacman"):
        return path in _pacman_core_paths([path])
    try:
        owner = subprocess.run(["dpkg", "-S", path], capture_output=True, text=True, timeout=5)
        if owner.returncode != 0 or not owner.stdout:
            return False
        pkg = owner.stdout.split(":", 1)[0].strip()
        prio = subprocess.run(["dpkg-query", "-W", "-f=${Priority}", pkg],
                              capture_output=True, text=True, timeout=5).stdout.strip()
        return prio in ("required", "important", "standard")
    except (OSError, subprocess.SubprocessError):
        return False


def core_package_paths(paths):
    """The subset of paths owned by a core system package -- the batched
    form of _core_package, two dpkg calls in total however many paths."""
    paths = [p for p in set(paths) if p.startswith("/usr/")]
    if not paths:
        return set()
    if not shutil.which("dpkg") and shutil.which("pacman"):
        return _pacman_core_paths(paths)
    try:
        out = subprocess.run(["dpkg", "-S", *paths], capture_output=True, text=True, timeout=60).stdout
        owners = {}
        for line in out.splitlines():
            if line.startswith("diversion ") or ": " not in line:
                continue
            pkgs, path = line.rsplit(": ", 1)
            owners[path] = [p.strip().split(":")[0] for p in pkgs.split(",")]
        pkgs = sorted({p for ps in owners.values() for p in ps})
        if not pkgs:
            return set()
        prio_out = subprocess.run(["dpkg-query", "-W", "-f=${Package} ${Priority}\\n", *pkgs],
                                  capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    core = {line.split()[0] for line in prio_out.splitlines()
            if len(line.split()) == 2 and line.split()[1] in ("required", "important", "standard")}
    return {path for path, ps in owners.items() if any(p in core for p in ps)}


# Windows programs that must never be blocked: the shell, sign-in and
# security, and what the lock and unlock steps themselves run. Blocking is
# by file name (focuslock_win), so a name here is protected wherever it is.
WIN_PROTECTED_NAMES = {
    "explorer.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "powershell_ise.exe", "conhost.exe",
    "windowsterminal.exe", "wt.exe", "openconsole.exe", "svchost.exe", "winlogon.exe", "csrss.exe",
    "lsass.exe", "services.exe", "smss.exe", "wininit.exe", "userinit.exe", "logonui.exe",
    "lockapp.exe", "dwm.exe", "sihost.exe", "ctfmon.exe", "fontdrvhost.exe", "audiodg.exe",
    "taskmgr.exe", "taskhostw.exe", "regedit.exe", "reg.exe", "mmc.exe", "consent.exe",
    "runtimebroker.exe", "searchhost.exe", "searchapp.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "textinputhost.exe", "systemsettings.exe", "applicationframehost.exe",
    "msiexec.exe", "rundll32.exe", "dllhost.exe", "schtasks.exe", "sc.exe", "icacls.exe",
    "ipconfig.exe", "wscript.exe", "cscript.exe", "msmpeng.exe", "securityhealthsystray.exe",
    "securityhealthservice.exe", "smartscreen.exe", "msedgewebview2.exe", "python.exe",
    "pythonw.exe", "py.exe", "pyw.exe", "focuslock.exe", "unins000.exe",
}
_WIN_UNSAFE_PATH_CHARS = re.compile(r'[\x00-\x1f*?"<>|]')


def win_exe_names(patterns):
    """The exact (lowercase) file names among WIN_APP_EXES-style entries."""
    return {p.lower() for p in patterns if "*" not in p}


def win_allowed_roots():
    """Folders custom Windows apps may live in (lowercase, ending in a backslash)."""
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
             os.path.join(os.environ.get("SystemDrive") or "C:", "\\Users")]
    return [os.path.normpath(r).lower().rstrip("\\") + "\\" for r in roots if r]


def _check_custom_path_windows(path):
    if not path or not os.path.isabs(path) or os.path.normpath(path) != path:
        return "Use a full path like C:\\Games\\Game\\game.exe."
    if _WIN_UNSAFE_PATH_CHARS.search(path[2:]):
        return "That path contains characters FocusLock can't safely handle."
    low = path.lower()
    if not low.endswith(".exe"):
        return "Pick the program's .exe file."
    if not low.startswith(tuple(win_allowed_roots())):
        return "Only programs in Program Files or your user folder."
    windir = os.path.normpath(os.environ.get("SystemRoot") or r"C:\Windows").lower() + "\\"
    if low.startswith((windir, SELF_DIR.lower() + "\\")):
        return "That's part of Windows or FocusLock itself."
    if not os.path.isfile(path):
        return "That isn't a program file."
    name = os.path.basename(low)
    builtin = set().union(*(win_exe_names(v) for v in WIN_APP_EXES.values()))
    if name in builtin:
        return "That's already one of the built-in apps -- pick it in Start Block instead."
    if name in WIN_PROTECTED_NAMES:
        return f"'{name}' is a system tool -- blocking it could break Windows."
    return None


def check_custom_path(path, home=None, core_paths=None):
    """None if path may be blocked, otherwise a short reason why not.
    core_paths, if given, is a precomputed core_package_paths() result
    (used by the scanner to avoid one dpkg call per candidate)."""
    if plat.IS_WINDOWS:
        return _check_custom_path_windows(path)
    home = (home or os.path.expanduser("~")).rstrip("/") + "/"
    if not path or not path.startswith("/") or os.path.normpath(path) != path:
        return "Use a full, plain path like /opt/game/game."
    if _UNSAFE_PATH_CHARS.search(path):
        return "That path contains characters FocusLock can't safely handle."
    if path.endswith(".focuslock-real"):
        return "That's FocusLock's own backup of a blocked program."
    if not (path.startswith(ALLOWED_DIRS) or path.startswith(home)):
        return "Only programs in /usr/bin, /usr/games, /usr/local/bin, /opt or your home folder."
    if path.startswith((home + ".config/", home + ".local/bin/hypr", SELF_DIR + "/")):
        return "That's part of your desktop setup or FocusLock itself."
    if not os.path.isfile(path) or not os.access(path, os.X_OK):
        return "That isn't an executable program file."
    for name in {os.path.basename(path).lower(), os.path.basename(os.path.realpath(path)).lower()}:
        if name in BUILTIN_NAMES:
            return "That's already one of the built-in apps -- pick it in Start Block instead."
        if name in PROTECTED_NAMES or name.startswith(PROTECTED_PREFIXES):
            return f"'{name}' is a system tool -- blocking it could break your system."
    if path.startswith("/usr/"):
        if core_paths is not None:
            is_core = path in core_paths or os.path.realpath(path) in core_paths
        else:
            is_core = _core_package(path) or _core_package(os.path.realpath(path))
        if is_core:
            return "That belongs to a core system package, so it can't be blocked."
    return None


def check_flatpak_id(app_id):
    if not _FLATPAK_ID.match(app_id or ""):
        return "That isn't a valid Flatpak app ID."
    if app_id in HIDDEN_FLATPAKS:
        return "That app is already blocked on every lock."
    return None


def installed_flatpaks():
    """[(app_id, name)] for installed Flatpak apps, minus the hidden ones."""
    try:
        out = subprocess.run(["flatpak", "list", "--app", "--columns=application,name"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    apps = []
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0] and parts[0] not in HIDDEN_FLATPAKS and not check_flatpak_id(parts[0]):
            apps.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else parts[0]))
    return sorted(apps, key=lambda a: a[1].lower())


def _running_programs_windows():
    try:
        import psutil
    except ImportError:
        return []
    import getpass
    me = getpass.getuser().lower()
    seen, found = set(), []
    for proc in psutil.process_iter(["exe", "username"]):
        exe, user = proc.info.get("exe"), (proc.info.get("username") or "")
        if not exe or exe in seen or user.rsplit("\\", 1)[-1].lower() != me:
            continue
        seen.add(exe)
        if any(h in os.path.basename(exe).lower() for h in _BACKGROUND_HINTS):
            continue
        if check_custom_path(exe) is None:
            found.append((os.path.basename(exe), exe))
    return sorted(found, key=lambda a: a[0].lower())


def running_programs():
    """[(name, exe_path)] of your own running programs that could be blocked."""
    if plat.IS_WINDOWS:
        return _running_programs_windows()
    seen, found = set(), []
    uid = os.getuid()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != uid:
                continue
            exe = os.readlink(f"/proc/{pid}/exe")
        except OSError:
            continue
        if exe in seen or exe.endswith(" (deleted)"):
            continue
        seen.add(exe)
        if any(h in os.path.basename(exe).lower() for h in _BACKGROUND_HINTS):
            continue
        if check_custom_path(exe) is None:
            found.append((os.path.basename(exe), exe))
    return sorted(found, key=lambda a: a[0].lower())


def all_apps():
    """Built-in apps plus your custom ones, as (key, label)."""
    return APPS + [(a["key"], a["name"]) for a in load_custom_apps()]


def dev_tool_keys():
    return set(DEV_TOOLS) | {a["key"] for a in load_custom_apps() if a.get("kind") == "dev"}


def custom_defs_arg(selected_keys):
    """The custom-app definitions apply.sh needs, one per line:
    key<TAB>name<TAB>path|flatpak<TAB>target."""
    lines = []
    for a in load_custom_apps():
        if a["key"] in selected_keys:
            lines.append("\t".join([a["key"], sanitize_app_name(a["name"]), a["source"], a["target"]]))
    return "\n".join(lines)


# ---------- custom websites ----------
# Blocked like the built-in sites, via /etc/hosts. focuslock-apply.sh
# re-validates every domain as root (keep its regex in sync with _DOMAIN).

_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
# Blocking these would break the lock itself, updates, or the desktop.
PROTECTED_DOMAINS = {"localhost", "localdomain", "ubuntu.com", "snapcraft.io", "flathub.org",
                     "debian.org", "canonical.com"}
if plat.IS_WINDOWS:
    PROTECTED_DOMAINS |= {"microsoft.com", "windows.com", "windowsupdate.com", "live.com",
                          "microsoftonline.com", "msftconnecttest.com"}


def load_custom_sites():
    return [s for s in _load_json(CUSTOM_SITES_FILE, []) if isinstance(s, dict) and "key" in s]


def save_custom_sites(sites):
    _save_json(CUSTOM_SITES_FILE, sites)


def normalize_domain(text):
    """'https://www.Reddit.com/r/x' -> 'reddit.com' (None if not a domain)."""
    text = (text or "").strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].split("@")[-1].split(":", 1)[0]
    text = text.strip(".")
    if text.startswith("www."):
        text = text[4:]
    return text or None


def check_domain(domain):
    """None if domain may be blocked, otherwise a short reason why not."""
    if not domain or not _DOMAIN.match(domain):
        return "That doesn't look like a website address (e.g. reddit.com)."
    if re.fullmatch(r"[0-9.]+", domain):
        return "Use the site's name, not an IP address."
    if any(domain == d or domain.endswith("." + d) for d in PROTECTED_DOMAINS):
        return "That domain is needed for system updates, so it can't be blocked."
    return None


def site_domains(domain):
    """The hosts entries that block a site: the domain and its www. form."""
    return [domain, "www." + domain]


def all_domains():
    """Built-in websites plus your custom ones, as (key, label)."""
    return DOMAINS + [(s["key"], s["name"]) for s in load_custom_sites()]


def custom_sites_arg(selected_keys):
    """What apply.sh needs, one site per line: key<TAB>name<TAB>space-separated domains."""
    return "\n".join("\t".join([s["key"], sanitize_app_name(s["name"]), " ".join(s["domains"])])
                     for s in load_custom_sites() if s["key"] in selected_keys)


# ---------- pomodoro (a timer only: it never blocks or unblocks anything) ----------

def load_pomo_plan():
    """{"phases": [{"name", "seconds", "accent"}], "rounds": n}. Empty until
    the user builds one -- there are deliberately no default phases."""
    plan = _load_json(POMO_PLAN_FILE, {})
    return {"phases": list(plan.get("phases", [])), "rounds": int(plan.get("rounds", 1) or 1)}


def save_pomo_plan(plan):
    _save_json(POMO_PLAN_FILE, plan)


def load_pomo_history():
    return _load_json(POMO_HISTORY_FILE, [])


def record_pomo(entry):
    """entry: started_at, ended_at, rounds_planned, rounds_done,
    seconds_done, completed (False if stopped early)."""
    history = load_pomo_history()
    history.append(entry)
    _save_json(POMO_HISTORY_FILE, history)
    return history


def pomo_stats(pomo_history):
    done = [p for p in pomo_history if p.get("completed")]
    return {
        "sessions": len(pomo_history),
        "completed": len(done),
        "stopped_early": len(pomo_history) - len(done),
        "rounds": sum(int(p.get("rounds_done", 0)) for p in pomo_history),
        "seconds": sum(int(p.get("seconds_done", 0)) for p in pomo_history),
    }


# ---------- weekly recap ----------

def _week_bounds(week_start):
    start = datetime.combine(week_start, datetime.min.time()).timestamp()
    return start, start + 7 * 86400


def week_recap(week_start, history, pomo_history, earned_badges, now=None):
    """Everything the weekly recap shows for the Monday-to-Sunday week
    starting at week_start (a date). Focus time is the part of each timed
    lock that fell inside the week (and before now)."""
    now = time.time() if now is None else now
    w0, w1 = _week_bounds(week_start)
    p0, p1 = _week_bounds(week_start - timedelta(days=7))
    per_day = [0] * 7
    sessions_per_day = [0] * 7
    prev_focus = 0
    sessions, notes = 0, []
    for s in history:
        try:
            start = date.fromisoformat(s["start"])
        except (KeyError, TypeError, ValueError):
            continue
        if week_start <= start < week_start + timedelta(days=7):
            sessions += 1
            sessions_per_day[start.weekday()] += 1
            note = (s.get("intent") or "").strip()
            if note and note not in notes:
                notes.append(note)
        bounds = session_bounds(s)
        if not bounds:
            continue
        a, b = bounds[0], min(bounds[1], now)
        for i in range(7):
            d0 = w0 + i * 86400
            per_day[i] += max(0, min(b, d0 + 86400) - max(a, d0))
        prev_focus += max(0, min(b, p1) - max(a, p0))
    pomo_rounds = pomo_secs = 0
    for p in pomo_history:
        if w0 <= p.get("started_at", 0) < w1:
            pomo_rounds += int(p.get("rounds_done", 0))
            pomo_secs += int(p.get("seconds_done", 0))
    focus = sum(per_day)
    best = None
    if focus:
        best = max(range(7), key=lambda i: per_day[i])
    elif sessions:
        best = max(range(7), key=lambda i: sessions_per_day[i])
    names = {b[0]: b[1] for b in BADGES}
    week_dates = {(week_start + timedelta(days=i)).isoformat() for i in range(7)}
    badges = [names[bid] for bid, when in (earned_badges or {}).items() if when in week_dates and bid in names]
    return {
        "week_start": week_start, "focus_seconds": focus, "prev_focus_seconds": prev_focus,
        "per_day": per_day, "sessions_per_day": sessions_per_day, "sessions": sessions, "best_day": best,
        "pomo_rounds": pomo_rounds, "pomo_seconds": pomo_secs, "badges": badges, "notes": notes[:3],
        "active": bool(sessions or pomo_rounds or focus),
    }


# ---------- badges ----------

# (id, name, how to earn it, icon, emblem text, accent, metric, target, unit)
# icon is drawn by the GUI; accent is "pink" | "cyan" | "yellow".
BADGES = [
    ("first_lock", "First Lock", "Start your first lock.", "lock", "1", "pink", "sessions", 1, ""),
    ("regular", "Regular", "Start 10 locks.", "lock", "10", "pink", "sessions", 10, ""),
    ("committed", "Committed", "Start 50 locks.", "lock", "50", "pink", "sessions", 50, ""),
    ("deep_hour", "Deep Hour", "Lock in for 1 hour or more in one session.", "clock", "1H", "cyan", "longest_hours", 1, "h"),
    ("all_day", "All Day", "One lock lasting 24 hours or more.", "clock", "24H", "cyan", "longest_hours", 24, "h"),
    ("iron_will", "Iron Will", "One lock lasting a full week.", "clock", "7D", "cyan", "longest_hours", 168, "h"),
    ("on_a_roll", "On a Roll", "Reach a 3-day streak.", "flame", "3", "yellow", "best_streak", 3, "d"),
    ("week_warrior", "Week Warrior", "Reach a 7-day streak.", "flame", "7", "yellow", "best_streak", 7, "d"),
    ("unstoppable", "Unstoppable", "Reach a 30-day streak.", "flame", "30", "yellow", "best_streak", 30, "d"),
    ("ten_hours", "Ten Hours In", "Focus for 10 hours in total.", "bolt", "10H", "pink", "focus_hours", 10, "h"),
    ("hundred_hours", "Hundred Club", "Focus for 100 hours in total.", "bolt", "100", "pink", "focus_hours", 100, "h"),
    ("clear_mind", "Clear Mind", "Write a focus note on 5 locks.", "note", "5", "cyan", "intents", 5, ""),
    ("early_bird", "Early Bird", "Start a lock between 4 and 8 AM.", "sun", "AM", "yellow", "early", 1, ""),
    ("night_owl", "Night Owl", "Start a lock at 10 PM or later.", "moon", "PM", "cyan", "late", 1, ""),
    ("weekend", "Weekend Warrior", "Lock in on 4 weekend days.", "star", "4", "yellow", "weekend", 4, ""),
    ("lockdown", "Total Lockdown", "Block every game, app and website in one lock.", "shield", "ALL", "pink", "lockdown", 1, ""),
    ("comeback", "Comeback", "Start a lock after a break of a week or more.", "star", "7+", "cyan", "comeback", 1, ""),
    ("first_pomodoro", "Tomato", "Finish a whole Pomodoro session.", "tomato", "1", "pink", "pomo_completed", 1, ""),
    ("ten_rounds", "Ten Rounds", "Finish 10 Pomodoro rounds.", "tomato", "10", "yellow", "pomo_rounds", 10, ""),
]


def badge_metrics(history, user_stats, now=None, pomo_history=None):
    """The numbers every badge is measured against."""
    st = compute_stats(history, now=now)
    ps = pomo_stats(pomo_history or [])
    non_dev_apps = {k for k, _ in APPS if k not in DEV_TOOLS}
    all_domains = {k for k, _ in DOMAINS}
    m = {
        "sessions": st["sessions"],
        "longest_hours": st["longest_seconds"] / 3600,
        "focus_hours": st["focus_seconds"] / 3600,
        "best_streak": user_stats.get("longest_streak", 0),
        "intents": 0, "early": 0, "late": 0, "weekend": 0, "lockdown": 0, "comeback": 0,
        "pomo_completed": ps["completed"], "pomo_rounds": ps["rounds"],
    }
    weekend_days = set()
    previous_end = None
    dated = []
    for s in history:
        try:
            dated.append((date.fromisoformat(s["start"]), date.fromisoformat(s.get("end", s["start"])), s))
        except (KeyError, TypeError, ValueError):
            continue
    for start, end, s in sorted(dated, key=lambda x: x[0]):
        if (s.get("intent") or "").strip():
            m["intents"] += 1
        if start.weekday() >= 5:
            weekend_days.add(start)
        if non_dev_apps <= set(s.get("apps", [])) and all_domains <= set(s.get("domains", [])):
            m["lockdown"] += 1
        if previous_end is not None and (start - previous_end).days >= 7:
            m["comeback"] += 1
        previous_end = max(previous_end or end, end)
        bounds = session_bounds(s)
        if bounds:
            hour = datetime.fromtimestamp(bounds[0]).hour
            if 4 <= hour < 8:
                m["early"] += 1
            if hour >= 22 or hour < 4:
                m["late"] += 1
    m["weekend"] = len(weekend_days)
    return m


def load_badges():
    """{badge_id: "YYYY-MM-DD" earned}, or None if badges were never synced."""
    if not os.path.exists(BADGES_FILE):
        return None
    return _load_json(BADGES_FILE, {})


def save_badges(earned):
    _save_json(BADGES_FILE, earned)


def sync_badges(history, user_stats, today=None, now=None, pomo_history=None):
    """Work out every badge's progress and record newly earned ones.

    Returns (badges, new_ids, first_run). badges is a list of dicts in
    BADGES order. A badge, once earned, stays earned. first_run is True the
    very first time this runs, when everything already earned from past
    history is recorded at once (the GUI announces that quietly rather than
    celebrating each one)."""
    today = (today or date.today()).isoformat()
    stored = load_badges()
    first_run = stored is None
    earned = dict(stored or {})
    metrics = badge_metrics(history, user_stats, now=now, pomo_history=pomo_history)
    badges, new_ids = [], []
    for bid, name, desc, icon, text, accent, metric, target, unit in BADGES:
        value = metrics.get(metric, 0)
        if bid not in earned and value >= target:
            earned[bid] = today
            new_ids.append(bid)
        badges.append({
            "id": bid, "name": name, "desc": desc, "icon": icon, "text": text, "accent": accent,
            "value": value, "target": target, "unit": unit,
            "earned": bid in earned, "earned_on": earned.get(bid),
        })
    if new_ids or first_run:
        save_badges(earned)
    return badges, new_ids, first_run


def notify(title, message):
    plat.notify(title, message)


def check_milestones(prev_stats, new_stats):
    """Fire a desktop notification for a new personal record or round number."""
    streak = new_stats["streak"]
    if streak > 1 and streak > prev_stats.get("longest_streak", 0):
        notify("FocusLock", f"New record! {streak}-day streak.")
    elif streak in MILESTONE_STREAKS:
        notify("FocusLock", f"{streak} days in a row!")
    if new_stats["total_sessions"] in MILESTONE_SESSIONS:
        notify("FocusLock", f"{new_stats['total_sessions']} focus sessions completed.")


# ---------- daily focus goal ----------
# Focused time for a day = the part of every timed lock that fell in that
# day (overlapping locks counted once), plus Pomodoro focus phases that
# didn't run during a lock. Breaks never count.

GOAL_CHOICES = [30, 60, 120, 180, 240, 300, 360, 480]   # minutes offered in the UI


def is_break_phase(phase):
    name = str(phase.get("name", "")).lower()
    return phase.get("accent") == "yellow" or "break" in name or "rest" in name


def _merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _day_bounds(day):
    start = datetime.combine(day, datetime.min.time()).timestamp()
    return start, start + 86400


def focus_seconds_on(day, history, pomo_history, now=None, live_pomo_focus=0):
    """Seconds focused on `day` (a date). live_pomo_focus: focus seconds of a
    Pomodoro that's running right now (not in history yet)."""
    now = time.time() if now is None else now
    d0, d1 = _day_bounds(day)
    end = min(d1, now)
    locks = []
    for s in history:
        bounds = session_bounds(s)
        if bounds:
            a, b = max(bounds[0], d0), min(bounds[1], end)
            if b > a:
                locks.append((a, b))
    locks = _merge(locks)
    total = sum(b - a for a, b in locks)
    for p in pomo_history:
        a = p.get("started_at")
        if not isinstance(a, (int, float)) or not d0 <= a < d1:
            continue
        focus = p.get("focus_seconds", p.get("seconds_done", 0)) or 0
        b = p.get("ended_at") if isinstance(p.get("ended_at"), (int, float)) else a + (p.get("seconds_done") or 0)
        span = max(1, b - a)
        overlap = sum(max(0, min(b, lb) - max(a, la)) for la, lb in locks)
        total += focus * max(0.0, 1 - overlap / span)
    return total + live_pomo_focus


def load_goals():
    data = _load_json(GOALS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("minutes", 0)
    met = data.get("met")
    data["met"] = met if isinstance(met, dict) else {}
    return data


def save_goals(goals):
    _save_json(GOALS_FILE, goals)


def record_goal_met(day, minutes):
    """Remember that the goal (of `minutes`) was reached on `day`. Returns
    True the first time for that day."""
    goals = load_goals()
    key = day.isoformat()
    if key in goals["met"]:
        return False
    goals["met"][key] = int(minutes)
    save_goals(goals)
    return True


def goal_streak(met, today=None):
    """Consecutive days the goal was met, ending today (or yesterday, if
    today isn't done yet)."""
    today = today or date.today()
    day = today if today.isoformat() in met else today - timedelta(days=1)
    streak = 0
    while day.isoformat() in met:
        streak += 1
        day -= timedelta(days=1)
    return streak


def goal_best_streak(met):
    days = sorted(date.fromisoformat(d) for d in met if _is_iso_date(d))
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def _is_iso_date(text):
    try:
        date.fromisoformat(text)
        return True
    except (TypeError, ValueError):
        return False


# ---------- session task list ----------
# A checklist for the lock that's running. Each lock gets a fresh list; the
# previous lock's list moves to "past" (kept short) when a new one starts.

TASK_MAX = 40
TASK_TEXT_MAX = 120
TASKS_PAST_KEEP = 60


def load_tasks():
    data = _load_json(TASKS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    tasks = data.get("tasks")
    data["tasks"] = [t for t in tasks if isinstance(t, dict) and isinstance(t.get("text"), str)] \
        if isinstance(tasks, list) else []
    data["past"] = data["past"] if isinstance(data.get("past"), list) else []
    data.setdefault("session", None)
    return data


def save_tasks(data):
    _save_json(TASKS_FILE, data)


def session_tasks(session_id):
    """The task list for this lock, starting a fresh one (and archiving the
    old) if the lock changed since the list was last used."""
    data = load_tasks()
    if data["session"] != session_id:
        if data["tasks"]:
            data["past"].append({"session": data["session"], "tasks": data["tasks"]})
            data["past"] = data["past"][-TASKS_PAST_KEEP:]
        data["session"], data["tasks"] = session_id, []
        save_tasks(data)
    return data


def task_counts(tasks):
    return sum(1 for t in tasks if t.get("done")), len(tasks)


# ---------- lock templates ----------
# A template fills in the LOCK tab in one click: duration, what to block,
# focus sound, session note and starter tasks. It never starts a lock by
# itself -- Start Block and the password still do that.
# apps: "default" (everything but dev tools), "everything", or a list of keys.

BUILTIN_TEMPLATES = [
    {"id": "deep_work", "name": "Deep work", "duration": [0, 4, 0], "apps": "default", "domains": "all",
     "sound": "brown", "intent": "", "tasks": []},
    {"id": "homework", "name": "Homework", "duration": [0, 2, 0], "apps": "everything", "domains": "all",
     "sound": "rain", "intent": "Homework", "tasks": []},
    {"id": "sprint", "name": "Quick sprint", "duration": [0, 0, 25], "apps": "default", "domains": "all",
     "sound": None, "intent": "", "tasks": []},
    {"id": "gamedev", "name": "Game dev", "duration": [0, 3, 0], "apps": "default", "domains": "all",
     "sound": "cafe", "intent": "Game dev", "tasks": []},
]
TEMPLATE_MAX = 12
TEMPLATE_NAME_MAX = 28


def _valid_template(t):
    try:
        d, h, m = (int(x) for x in t["duration"])
    except (KeyError, TypeError, ValueError):
        return False
    return (isinstance(t.get("id"), str) and isinstance(t.get("name"), str) and t["name"].strip()
            and 0 <= d <= 30 and 0 <= h <= 23 and 0 <= m <= 59 and (d or h or m)
            and (t.get("apps") in ("default", "everything") or isinstance(t.get("apps"), list))
            and (t.get("domains") == "all" or isinstance(t.get("domains"), list))
            and isinstance(t.get("tasks", []), list))


def load_templates():
    """The user's own templates (built-ins are BUILTIN_TEMPLATES)."""
    data = _load_json(TEMPLATES_FILE, [])
    return [t for t in data if isinstance(t, dict) and _valid_template(t)] if isinstance(data, list) else []


def save_templates(templates):
    _save_json(TEMPLATES_FILE, templates[:TEMPLATE_MAX])


def template_selection(template, app_keys, dev_keys, domain_keys):
    """(apps, domains) a template turns on, limited to what exists now."""
    apps = template.get("apps")
    if apps == "everything":
        chosen_apps = set(app_keys)
    elif apps == "default":
        chosen_apps = set(app_keys) - set(dev_keys)
    else:
        chosen_apps = set(apps) & set(app_keys)
    domains = template.get("domains")
    chosen_domains = set(domain_keys) if domains == "all" else set(domains) & set(domain_keys)
    return chosen_apps, chosen_domains


# ---------- distraction log ----------
# focuslock-apply.sh's blocking wrappers append "<epoch>\t<app key>" to this
# file (in the launching user's state dir) each time a blocked app is
# started. Websites can't be logged: they're blocked in /etc/hosts, so a
# browser just fails to connect and nothing of ours runs.

ATTEMPTS_MAX_LINES = 20000
ATTEMPT_MERGE_SECONDS = 5     # a launcher retrying within seconds is one attempt
SITE_MERGE_SECONDS = 60       # browsers retry and preconnect a lot: one site, one minute, one attempt


def attempts_path():
    return os.path.join(plat.STATE_DIR, "attempts.log")


def site_key_for_host(host, groups):
    """The website key (e.g. "discord_web") a hostname belongs to, or None."""
    for key, domains in groups.items():
        for d in domains:
            if host == d or host.endswith("." + d):
                return key
    return None


def _read_log_lines(path):
    try:
        with open(path, errors="replace") as f:
            return f.readlines()[-ATTEMPTS_MAX_LINES:]
    except OSError:
        return []


def load_attempts(path=None, site_log=None):
    """[(epoch, key)] oldest first: blocked apps from the user's log (and on
    Windows, apps the guard task had to close), plus blocked websites from
    the site logger's log (hostnames mapped to site keys). Rapid repeats of
    the same app/site count once."""
    raw = []
    app_logs = [path or attempts_path()]
    if path is None and plat.GUARD_LOG:
        app_logs.append(plat.GUARD_LOG)
    for log in app_logs:
        for line in _read_log_lines(log):
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and parts[0].isdigit() and re.fullmatch(r"[a-z0-9_]{1,48}", parts[1]):
                raw.append((int(parts[0]), parts[1]))
    site_log = site_log or SITELOG_FILE
    site_lines = _read_log_lines(site_log) if site_log else []
    if site_lines:
        groups = domain_groups()
        for line in site_lines:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and parts[0].isdigit():
                key = site_key_for_host(parts[1].strip().lower(), groups)
                if key:
                    raw.append((int(parts[0]), key))
    raw.sort()
    sites = set(domain_groups()) if site_lines else set()
    out, last = [], {}
    for ts, key in raw:
        window = SITE_MERGE_SECONDS if key in sites else ATTEMPT_MERGE_SECONDS
        if ts - last.get(key, -10 ** 12) >= window:
            out.append((ts, key))
        last[key] = ts
    return out


def save_attempts(attempts, path=None):
    path = path or attempts_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for ts, key in attempts[-ATTEMPTS_MAX_LINES:]:
            if isinstance(ts, int) and isinstance(key, str) and re.fullmatch(r"[a-z0-9_]{1,48}", key):
                f.write(f"{ts}\t{key}\n")
    os.replace(tmp, path)


def log_attempt(key, ts=None, path=None):
    """Append one attempt (what the wrappers write), unless the same app was
    already logged within ATTEMPT_MERGE_SECONDS -- e.g. by the wrapper itself."""
    if not re.fullmatch(r"[a-z0-9_]{1,48}", key or ""):
        return False
    ts = int(time.time()) if ts is None else int(ts)
    if any(k == key and abs(t - ts) < ATTEMPT_MERGE_SECONDS for t, k in load_attempts(path)[-50:]):
        return False
    path = path or attempts_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(f"{ts}\t{key}\n")
    return True


def attempt_summary(attempts, since=0, until=None):
    """Counts for attempts in [since, until): total, per app (most first),
    per hour of day, and the latest one."""
    until = time.time() if until is None else until
    picked = [(ts, k) for ts, k in attempts if since <= ts < until]
    per_app = Counter(k for _, k in picked)
    per_hour = [0] * 24
    for ts, _ in picked:
        per_hour[datetime.fromtimestamp(ts).hour] += 1
    return {"total": len(picked), "per_app": per_app.most_common(), "per_hour": per_hour,
            "last": picked[-1] if picked else None}


# ---------- levels & XP ----------
# XP is worked out from what's already recorded (history, Pomodoros, goals,
# tasks, badges, the distraction log) rather than stored, so it can't drift
# and a restored backup brings the right level with it. Nothing takes XP away.

XP_PER_FOCUS_MINUTE = 1
XP_LOCK_START = 20
XP_LOCK_STARTS_PER_DAY = 3     # more than this a day earns nothing extra
XP_GOAL_DAY = 50
XP_TASK = 5
XP_TASKS_PER_LOCK = 10         # ticked tasks counted per lock
XP_BADGE = 100
XP_POMODORO = 25
XP_CLEAN_LOCK = 30
XP_FOCUS_DAY_CAP = 8 * 3600    # focus counted for XP per calendar day: a week-long lock isn't 24 h/day of work

LEVEL_TITLES = [(1, "Distracted"), (3, "Getting There"), (5, "Focused"), (8, "Deep Worker"),
                (12, "Flow State"), (16, "Monk Mode"), (20, "Unshakeable"), (30, "Legend")]
# Themes earned by levelling up (the rest are always available).
THEME_UNLOCKS = {"sunset": 3, "gold": 6, "aurora": 10}


def xp_to_reach(level):
    """Total XP needed to reach `level` (level 1 is free): 100, 300, 600, 1000, ..."""
    return 50 * (level - 1) * level


def level_for(xp):
    level = 1
    while xp >= xp_to_reach(level + 1):
        level += 1
    return level


def level_title(level):
    title = LEVEL_TITLES[0][1]
    for at, name in LEVEL_TITLES:
        if level >= at:
            title = name
    return title


def focus_by_day(history, pomo_history, now=None):
    """{date: seconds focused that day}: locks (overlaps counted once, running
    ones up to now) split at midnight, plus Pomodoro focus phases that
    didn't run during a lock (counted on the day they started)."""
    now = time.time() if now is None else now
    locks = []
    for s in history:
        b = session_bounds(s)
        if b and min(b[1], now) > b[0]:
            locks.append((b[0], min(b[1], now)))
    locks = _merge(locks)
    days = Counter()
    for a, b in locks:
        while a < b:
            day = date.fromtimestamp(a)
            cut = min(b, _day_bounds(day)[1])
            days[day] += cut - a
            a = cut
    for p in pomo_history:
        a = p.get("started_at")
        if not isinstance(a, (int, float)):
            continue
        focus = p.get("focus_seconds", p.get("seconds_done", 0)) or 0
        b = p.get("ended_at") if isinstance(p.get("ended_at"), (int, float)) else a + (p.get("seconds_done") or 0)
        overlap = sum(max(0, min(b, lb) - max(a, la)) for la, lb in locks)
        days[date.fromtimestamp(a)] += focus * max(0.0, 1 - overlap / max(1, b - a))
    return days


def total_focus_seconds(history, pomo_history, now=None, day_cap=None):
    """All focused time ever; with day_cap, each day counts at most that much."""
    days = focus_by_day(history, pomo_history, now)
    return sum(min(v, day_cap) if day_cap else v for v in days.values())


# ---------- focus rewards ----------
# Things unlocked by total focus hours (counted like XP: at most 8 h a day,
# so a week-long lock doesn't unlock everything at once). Worked out from the
# records, so a restored backup brings them back too.
# (hours, kind, key, name, description); kind: sound | font | theme | celebration

REWARDS = [
    (5, "sound", "library", "Library", "A quiet reading room: soft air, pages turning, distant footsteps."),
    (10, "font", "commodore", "Commodore", "The C-64's chunky 8-bit lettering."),
    (20, "celebration", "fireworks", "Fireworks", "Lock in under a sky full of fireworks."),
    (35, "theme", "midnight", "Midnight", "Deep navy with a warm gold accent."),
    (50, "sound", "space", "Space station", "A low hull hum, air vents and distant beeps."),
    (75, "font", "amiga", "Amiga", "Topaz, the Amiga's classic system font."),
    (100, "celebration", "starfall", "Starfall", "Stars rain down as the lock snaps shut."),
    (150, "theme", "sakura", "Sakura", "Soft cherry-blossom pink, light and calm."),
    (200, "sound", "train", "Night train", "Wheels over rail joints in a quiet carriage."),
    (300, "font", "ocr", "OCR", "OCR-A, the font made for machines to read."),
    (400, "theme", "matrix", "Matrix", "Green on black. You know the one."),
    (500, "celebration", "supernova", "Supernova", "A blinding burst, for the truly dedicated."),
]


def focus_hours(history, pomo_history, now=None):
    return total_focus_seconds(history, pomo_history, now, day_cap=XP_FOCUS_DAY_CAP) / 3600


def reward_for(kind, key):
    """The reward that unlocks this item, or None if it's always available."""
    return next((r for r in REWARDS if r[1] == kind and r[2] == key), None)


def unlocked_rewards(hours):
    return [r for r in REWARDS if hours >= r[0]]


# ---------- weekly challenges ----------
# Three a week (Monday to Sunday), picked from CHALLENGES by the week's date so
# everyone's week is stable and nothing needs storing. Progress is worked out
# from the same records as everything else; finished ones add XP.

CHALLENGES = {
    "clean_locks": ("Finish {n} locks without reaching for a blocked app", 3, 150),
    "focus_hours": ("Focus for {n} hours", 10, 150),
    "tasks_done": ("Tick off {n} tasks", 15, 100),
    "lock_days": ("Lock in on {n} different days", 5, 150),
    "early_bird": ("Start a lock before 9 am on {n} days", 2, 100),
    "pomodoros": ("Finish {n} Pomodoros", 3, 100),
    "goal_days": ("Hit your daily goal on {n} days", 4, 150),
}
CHALLENGES_PER_WEEK = 3


def week_start_of(day):
    return day - timedelta(days=day.weekday())


def challenges_for_week(week_start):
    import random
    return random.Random(week_start.toordinal()).sample(sorted(CHALLENGES), CHALLENGES_PER_WEEK)


def _all_tasks(task_data):
    lists = [task_data.get("tasks", [])] + [p.get("tasks", []) for p in task_data.get("past", []) if isinstance(p, dict)]
    return [t for lst in lists if isinstance(lst, list) for t in lst if isinstance(t, dict)]


def challenge_progress(week_start, history, pomo_history, goals_met, task_data, attempts, clean_since=None, now=None):
    """[{id, text, value, target, xp, done}] for that week's challenges."""
    now = time.time() if now is None else now
    w0 = datetime.combine(week_start, datetime.min.time()).timestamp()
    w1 = w0 + 7 * 86400
    days = [week_start + timedelta(days=i) for i in range(7)]
    attempt_times = sorted(ts for ts, _ in attempts)
    out = []
    for cid in challenges_for_week(week_start):
        text, target, xp = CHALLENGES[cid]
        if cid == "clean_locks":
            value = 0
            for s in history:
                b = session_bounds(s)
                if not b or not w0 <= b[0] < w1 or b[1] > now or (clean_since is not None and b[0] < clean_since):
                    continue
                lo = bisect.bisect_left(attempt_times, b[0])
                if lo >= len(attempt_times) or attempt_times[lo] >= b[1]:
                    value += 1
        elif cid == "focus_hours":
            by_day = focus_by_day(history, pomo_history, now)
            value = round(sum(min(by_day.get(d, 0), XP_FOCUS_DAY_CAP) for d in days) / 3600, 1)
        elif cid == "tasks_done":
            value = sum(1 for t in _all_tasks(task_data) if t.get("done") and isinstance(t.get("done_at"), (int, float))
                        and w0 <= t["done_at"] < w1)
        elif cid == "lock_days":
            value = len({s.get("start") for s in history if s.get("start") in {d.isoformat() for d in days}})
        elif cid == "early_bird":
            value = len({date.fromtimestamp(b[0]) for b in (session_bounds(s) for s in history)
                         if b and w0 <= b[0] < w1 and datetime.fromtimestamp(b[0]).hour < 9})
        elif cid == "pomodoros":
            value = sum(1 for p in pomo_history if p.get("completed") and isinstance(p.get("started_at"), (int, float))
                        and w0 <= p["started_at"] < w1)
        else:   # goal_days
            value = sum(1 for d in days if d.isoformat() in goals_met)
        out.append({"id": cid, "text": text.format(n=target), "value": value, "target": target, "xp": xp,
                    "done": value >= target})
    return out


def day_details(day, history, pomo_history, goals_met, task_data, attempts, now=None):
    """Everything recorded for one calendar day, for the Stats calendar."""
    now = time.time() if now is None else now
    d0, d1 = _day_bounds(day)
    locks = []
    for s in history:
        b = session_bounds(s)
        if b and b[0] < d1 and b[1] > d0:
            locks.append({"start": b[0], "end": b[1], "intent": (s.get("intent") or "").strip(),
                          "blocked": len(s.get("apps", [])) + len(s.get("domains", [])), "running": b[1] > now})
        elif not b and s.get("start") == day.isoformat():
            locks.append({"start": None, "end": None, "intent": (s.get("intent") or "").strip(),
                          "blocked": len(s.get("apps", [])) + len(s.get("domains", [])), "running": False})
    pomos = [{"start": p["started_at"], "focus": p.get("focus_seconds", p.get("seconds_done", 0)) or 0,
              "rounds": p.get("rounds_done", 0), "completed": bool(p.get("completed"))}
             for p in pomo_history if isinstance(p.get("started_at"), (int, float)) and d0 <= p["started_at"] < d1]
    tasks = [t["text"] for t in _all_tasks(task_data)
             if t.get("done") and isinstance(t.get("done_at"), (int, float)) and d0 <= t["done_at"] < d1]
    per_app = Counter(k for ts, k in attempts if d0 <= ts < d1)
    return {"focus": focus_seconds_on(day, history, pomo_history, now), "locks": sorted(locks, key=lambda l: l["start"] or 0),
            "pomos": pomos, "tasks": tasks, "attempts": per_app.most_common(), "goal": goals_met.get(day.isoformat())}


def challenge_xp(history, pomo_history, goals_met, task_data, attempts, clean_since=None, now=None):
    """XP from every finished weekly challenge, from the first week with any record to now."""
    now = time.time() if now is None else now
    stamps = [b[0] for b in (session_bounds(s) for s in history) if b]
    stamps += [p["started_at"] for p in pomo_history if isinstance(p.get("started_at"), (int, float))]
    if not stamps:
        return 0
    week = week_start_of(date.fromtimestamp(min(stamps)))
    last = week_start_of(date.fromtimestamp(now))
    total = 0
    while week <= last:
        total += sum(c["xp"] for c in challenge_progress(week, history, pomo_history, goals_met, task_data,
                                                         attempts, clean_since, now) if c["done"])
        week += timedelta(days=7)
    return total


def compute_xp(history, pomo_history, goals_met, task_data, earned_badges, attempts, clean_since=None, now=None):
    """Total XP with a breakdown: [(label, xp)], biggest first."""
    now = time.time() if now is None else now
    focus_min = int(total_focus_seconds(history, pomo_history, now, day_cap=XP_FOCUS_DAY_CAP) // 60)
    starts_per_day = Counter(s.get("start") for s in history if s.get("start"))
    lock_starts = sum(min(n, XP_LOCK_STARTS_PER_DAY) for n in starts_per_day.values())
    task_lists = [task_data.get("tasks", [])] + [p.get("tasks", []) for p in task_data.get("past", [])
                                                  if isinstance(p, dict)]
    tasks_done = sum(min(XP_TASKS_PER_LOCK, sum(1 for t in lst if isinstance(t, dict) and t.get("done")))
                     for lst in task_lists if isinstance(lst, list))
    pomos = sum(1 for p in pomo_history if p.get("completed"))
    attempt_times = sorted(ts for ts, _ in attempts)
    clean = 0
    for s in history:
        b = session_bounds(s)
        if not b or b[1] > now or (clean_since is not None and b[0] < clean_since):
            continue   # only finished locks, and only since the log has existed
        lo = bisect.bisect_left(attempt_times, b[0])
        if lo >= len(attempt_times) or attempt_times[lo] >= b[1]:
            clean += 1
    parts = [("Focused minutes (up to 8 h a day)", focus_min * XP_PER_FOCUS_MINUTE),
             ("Locks started", lock_starts * XP_LOCK_START),
             ("Daily goals met", len(goals_met) * XP_GOAL_DAY),
             ("Tasks ticked off", tasks_done * XP_TASK),
             ("Badges", len(earned_badges or {}) * XP_BADGE),
             ("Pomodoros finished", pomos * XP_POMODORO),
             ("Clean locks (no distractions)", clean * XP_CLEAN_LOCK),
             ("Weekly challenges", challenge_xp(history, pomo_history, goals_met, task_data, attempts,
                                                clean_since, now))]
    total = sum(x for _, x in parts)
    level = level_for(total)
    return {"total": total, "parts": sorted(parts, key=lambda p: -p[1]), "level": level,
            "title": level_title(level), "level_start": xp_to_reach(level), "level_end": xp_to_reach(level + 1),
            "next_title": level_title(level + 1) if level_title(level + 1) != level_title(level) else None}


# ---------- CSV export ----------

def _iso(ts):
    return datetime.fromtimestamp(ts).isoformat(timespec="minutes") if isinstance(ts, (int, float)) else ""


def export_daily_csv(path, history, pomo_history, goals_met, task_data, attempts, now=None):
    """One row per day from the first record to today. Returns the row count."""
    import csv
    now = time.time() if now is None else now
    by_day = focus_by_day(history, pomo_history, now)
    starts = Counter(s.get("start") for s in history if s.get("start"))
    pomos = Counter(date.fromtimestamp(p["started_at"]).isoformat() for p in pomo_history
                    if isinstance(p.get("started_at"), (int, float)))
    tasks = Counter(date.fromtimestamp(t["done_at"]).isoformat() for t in _all_tasks(task_data)
                    if t.get("done") and isinstance(t.get("done_at"), (int, float)))
    tries = Counter(date.fromtimestamp(ts).isoformat() for ts, _ in attempts)
    days = [d for d in by_day] + [date.fromisoformat(x) for x in list(starts) + list(pomos) + list(tasks) + list(tries)
                                  + list(goals_met) if _is_iso_date(x)]
    if not days:
        days = [date.today()]
    first, last = min(days), date.fromtimestamp(now)
    rows = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "weekday", "focused_minutes", "locks_started", "pomodoros", "goal_met", "goal_minutes",
                    "tasks_done", "distraction_attempts"])
        day = first
        while day <= last:
            key = day.isoformat()
            w.writerow([key, day.strftime("%A"), int(by_day.get(day, 0) // 60), starts.get(key, 0), pomos.get(key, 0),
                        "yes" if key in goals_met else "no", goals_met.get(key, ""), tasks.get(key, 0),
                        tries.get(key, 0)])
            rows += 1
            day += timedelta(days=1)
    return rows


def export_sessions_csv(path, history, pomo_history, app_names, site_names, now=None):
    """One row per lock and per Pomodoro, oldest first. Returns the row count."""
    import csv
    now = time.time() if now is None else now
    rows = []
    for s in history:
        b = session_bounds(s)
        start = b[0] if b else None
        minutes = int((min(b[1], now) - b[0]) // 60) if b else ""
        rows.append((start or 0, ["lock", s.get("start", ""), _iso(start), _iso(b[1] if b else None), minutes,
                                  "; ".join(app_names.get(k, k) for k in s.get("apps", [])),
                                  "; ".join(site_names.get(k, k) for k in s.get("domains", [])),
                                  (s.get("intent") or "").strip(), "running" if b and b[1] > now else "", "", ""]))
    for p in pomo_history:
        a = p.get("started_at")
        if not isinstance(a, (int, float)):
            continue
        focus = p.get("focus_seconds", p.get("seconds_done", 0)) or 0
        rows.append((a, ["pomodoro", date.fromtimestamp(a).isoformat(), _iso(a), _iso(p.get("ended_at")),
                         int(focus // 60), "", "", "", "finished" if p.get("completed") else "stopped early",
                         p.get("rounds_done", ""), p.get("rounds_planned", "")]))
    rows.sort(key=lambda r: r[0])
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["type", "date", "start", "end", "focused_minutes", "apps_blocked", "websites_blocked", "note",
                    "status", "rounds_done", "rounds_planned"])
        for _, row in rows:
            w.writerow(row)
    return len(rows)


# ---------- backup / restore ----------
# A backup is one JSON file holding every user data file above. The lock
# itself lives in root-owned LOCKDIR and is never part of a backup, so
# restoring can't start, change or end a lock.

BACKUP_KIND = "focuslock-backup"
BACKUP_VERSION = 1
BACKUPS_DIR = os.path.join(CONFIG_DIR, "backups")
BACKUP_MAX_BYTES = 20 * 1024 * 1024
# name -> (path, expected JSON type, what it is, for messages)
BACKUP_FILES = {
    "settings": (SETTINGS_FILE, dict, "settings and theme"),
    "stats": (STATS_FILE, dict, "streaks"),
    "history": (HISTORY_FILE, list, "lock history"),
    "presets": (PRESETS_FILE, dict, "presets"),
    "badges": (BADGES_FILE, dict, "badges"),
    "pomodoro_plan": (POMO_PLAN_FILE, dict, "Pomodoro plan"),
    "pomodoro_history": (POMO_HISTORY_FILE, list, "Pomodoro history"),
    "custom_apps": (CUSTOM_APPS_FILE, list, "added apps"),
    "custom_sites": (CUSTOM_SITES_FILE, list, "added websites"),
    "goals": (GOALS_FILE, dict, "daily goal"),
    "tasks": (TASKS_FILE, dict, "task lists"),
    "templates": (TEMPLATES_FILE, list, "lock templates"),
}


def make_backup():
    """Everything restorable, as one dict. Missing or unreadable files are skipped."""
    files = {}
    attempts = load_attempts()
    if attempts:
        files["distractions"] = [[ts, key] for ts, key in attempts]
    for name, (path, kind, _) in BACKUP_FILES.items():
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, kind):
            files[name] = data
    return {"kind": BACKUP_KIND, "version": BACKUP_VERSION,
            "created": datetime.now().isoformat(timespec="seconds"), "files": files}


def _write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def write_backup(path):
    backup = make_backup()
    _write_json_atomic(path, backup)
    return backup


def read_backup(path):
    """Load and check a backup file. Raises ValueError with a message meant
    for the user if it isn't a usable FocusLock backup."""
    try:
        if os.path.getsize(path) > BACKUP_MAX_BYTES:
            raise ValueError("That file is too big to be a FocusLock backup.")
        with open(path) as f:
            backup = json.load(f)
    except OSError as e:
        raise ValueError(f"Couldn't read that file ({e.strerror or e}).")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("That file isn't a FocusLock backup (it's not valid JSON).")
    if not isinstance(backup, dict) or backup.get("kind") != BACKUP_KIND:
        raise ValueError("That file isn't a FocusLock backup.")
    if not isinstance(backup.get("version"), int) or backup["version"] > BACKUP_VERSION:
        raise ValueError("That backup was made by a newer FocusLock -- update FocusLock to restore it.")
    files = backup.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("That backup is empty.")
    for name, data in files.items():
        if name == "distractions":
            if not isinstance(data, list) or not all(isinstance(x, list) and len(x) == 2 for x in data):
                raise ValueError("That backup's distraction log is damaged, so nothing was restored.")
            continue
        if name not in BACKUP_FILES:
            continue   # from a newer version; ignored
        if not isinstance(data, BACKUP_FILES[name][1]):
            raise ValueError(f"That backup's {BACKUP_FILES[name][2]} are damaged, so nothing was restored.")
    return backup


def restore_backup(backup):
    """Write a backup (from read_backup) over the current data. Files the
    backup doesn't include are left as they are. Returns what was restored."""
    restored = []
    for name, data in backup["files"].items():
        if name == "distractions":
            save_attempts([(int(ts), str(key)) for ts, key in data if isinstance(ts, (int, float))])
            restored.append("distraction log")
        elif name in BACKUP_FILES:
            _write_json_atomic(BACKUP_FILES[name][0], data)
            restored.append(BACKUP_FILES[name][2])
    return restored


def safety_backup(keep=5):
    """Save the current data to BACKUPS_DIR before a restore overwrites it,
    keeping only the newest few. Returns the path."""
    path = os.path.join(BACKUPS_DIR, f"before-restore-{datetime.now():%Y%m%d-%H%M%S}.json")
    write_backup(path)
    old = sorted(f for f in os.listdir(BACKUPS_DIR) if f.startswith("before-restore-") and f.endswith(".json"))
    for name in old[:-keep]:
        try:
            os.remove(os.path.join(BACKUPS_DIR, name))
        except OSError:
            pass
    return path
