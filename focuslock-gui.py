#!/usr/bin/env python3
"""FocusLock GUI -- pick a duration and what to block, then engage the lock.

Wraps the existing focuslock-apply.sh / focuslock-unlock.sh /
focuslock-youtube-break-apply.sh shell scripts. No early-unlock control is
offered anywhere in this UI, on purpose: that decision was made deliberately
by whoever set this tool up, and the GUI does not get to override it either.
"""
import colorsys
import math
import os
import random
import subprocess
import sys
import threading
import time
import re
import tkinter as tk
from tkinter import filedialog, font as tkfont
from datetime import datetime, date, timedelta

import focuslock_ambient as ambient
import focuslock_platform as plat
import focuslock_anim as anim
import focuslock_scan as scanner
import focuslock_sound as snd
import focuslock_watch
from focuslock_core import (
    SELF_DIR, watcher_command, UNLOCK_AT_FILE, LAST_USED_FILE, UNTIL_FILE, INTENT_FILE,
    APPS, DOMAINS, DEV_TOOLS,
    read_file, run_date, parse_unlock_time, detect_blocked_apps, detect_blocked_domains, lock_progress,
    load_stats, bump_streak, load_presets, save_presets,
    load_history, record_session, locked_days_from_history, check_milestones,
    compute_stats, session_bounds, sync_badges, load_settings, save_settings, notify,
    load_pomo_plan, save_pomo_plan, load_pomo_history, record_pomo, pomo_stats,
    all_apps, dev_tool_keys, load_custom_apps, save_custom_apps, check_custom_path, check_flatpak_id,
    installed_flatpaks, running_programs, custom_defs_arg, sanitize_app_name, make_custom_key, CUSTOM_KINDS,
    core_package_paths, all_domains, load_custom_sites, save_custom_sites, normalize_domain, check_domain,
    site_domains, custom_sites_arg, DOMAIN_GROUPS, week_recap, load_badges,
    write_backup, read_backup, restore_backup, safety_backup, BACKUP_FILES,
    is_break_phase, focus_seconds_on, load_goals, save_goals, record_goal_met, goal_streak, goal_best_streak,
    GOAL_CHOICES, load_tasks, save_tasks, session_tasks, task_counts, TASK_MAX, TASK_TEXT_MAX,
    load_attempts, attempt_summary, attempts_path,
    BUILTIN_TEMPLATES, load_templates, save_templates, template_selection, TEMPLATE_MAX, TEMPLATE_NAME_MAX,
    compute_xp, THEME_UNLOCKS, challenge_progress, week_start_of, focus_by_day, day_details,
    export_daily_csv, export_sessions_csv,
    SITELOG_ADDR, HOSTS_FILE, REWARDS, focus_hours, reward_for, unlocked_rewards,
)

# ---------- theming ----------
# Two full palettes; apply_theme() reassigns the module-level names every
# widget-building function reads, then the caller rebuilds the UI.
_THEMES = {
    "dark": {
        "BG": "#242424", "SURFACE": "#2d2d2d", "SURFACE_2": "#383838",
        "BORDER": "#4a4a4a", "BORDER_STRONG": "#5c5c5c",
        "INK": "#f0f0f0", "INK_DIM": "#b0b0b0", "INK_FAINT": "#828282",
        "PINK": "#ff2e9a", "CYAN": "#00d0e8", "YELLOW": "#ffe156",
        "ON_PINK": "#1a0512", "ON_CYAN": "#031418", "ON_YELLOW": "#241c33",
    },
    "light": {
        "BG": "#f0f0f0", "SURFACE": "#ffffff", "SURFACE_2": "#e6e6e6",
        "BORDER": "#cfcfcf", "BORDER_STRONG": "#b5b5b5",
        "INK": "#202020", "INK_DIM": "#555555", "INK_FAINT": "#828282",
        "PINK": "#d81b78", "CYAN": "#00838f", "YELLOW": "#a87900",
        "ON_PINK": "#ffffff", "ON_CYAN": "#ffffff", "ON_YELLOW": "#ffffff",
    },
    "synthwave": {
        "BG": "#1a1028", "SURFACE": "#241638", "SURFACE_2": "#2f1d4a",
        "BORDER": "#45306a", "BORDER_STRONG": "#5a4185",
        "INK": "#f6ecff", "INK_DIM": "#c4b0e0", "INK_FAINT": "#8c79ab",
        "PINK": "#ff3ea5", "CYAN": "#2de2e6", "YELLOW": "#ffd319",
        "ON_PINK": "#1a0512", "ON_CYAN": "#04181a", "ON_YELLOW": "#241c05",
    },
    "ocean": {
        "BG": "#0e1726", "SURFACE": "#142035", "SURFACE_2": "#1b2a44",
        "BORDER": "#273a5c", "BORDER_STRONG": "#34507a",
        "INK": "#e8f1ff", "INK_DIM": "#a3b7d4", "INK_FAINT": "#7184a3",
        "PINK": "#ff6b9a", "CYAN": "#38bdf8", "YELLOW": "#fbbf24",
        "ON_PINK": "#22060f", "ON_CYAN": "#04121c", "ON_YELLOW": "#231a03",
    },
    "forest": {
        "BG": "#16201a", "SURFACE": "#1d2a22", "SURFACE_2": "#26362c",
        "BORDER": "#35493b", "BORDER_STRONG": "#46604f",
        "INK": "#eaf3eb", "INK_DIM": "#abc2af", "INK_FAINT": "#7b947f",
        "PINK": "#ff8a5b", "CYAN": "#4fd1a5", "YELLOW": "#e8c547",
        "ON_PINK": "#230d03", "ON_CYAN": "#04170f", "ON_YELLOW": "#231c04",
    },
    "paper": {
        "BG": "#f4efe6", "SURFACE": "#fffaf2", "SURFACE_2": "#ebe3d6",
        "BORDER": "#d6cab7", "BORDER_STRONG": "#bfb19b",
        "INK": "#2b2620", "INK_DIM": "#5e554a", "INK_FAINT": "#8c8273",
        "PINK": "#c2410c", "CYAN": "#0f766e", "YELLOW": "#a16207",
        "ON_PINK": "#ffffff", "ON_CYAN": "#ffffff", "ON_YELLOW": "#ffffff",
    },
    # Reward themes, unlocked by levelling up (THEME_UNLOCKS).
    "sunset": {
        "BG": "#1f1420", "SURFACE": "#2a1a2a", "SURFACE_2": "#362236",
        "BORDER": "#4d3048", "BORDER_STRONG": "#643e5c",
        "INK": "#fff1ea", "INK_DIM": "#e0bfb4", "INK_FAINT": "#a8867f",
        "PINK": "#ff6f59", "CYAN": "#ffb347", "YELLOW": "#ffd6a5",
        "ON_PINK": "#240a05", "ON_CYAN": "#241503", "ON_YELLOW": "#241a0c",
    },
    "gold": {
        "BG": "#15130d", "SURFACE": "#1e1b12", "SURFACE_2": "#29251a",
        "BORDER": "#3d3725", "BORDER_STRONG": "#544b31",
        "INK": "#fbf3dc", "INK_DIM": "#d4c69c", "INK_FAINT": "#9a8f6c",
        "PINK": "#e6b422", "CYAN": "#f5d77a", "YELLOW": "#fff1b8",
        "ON_PINK": "#1a1405", "ON_CYAN": "#1a1405", "ON_YELLOW": "#1a1405",
    },
    "aurora": {
        "BG": "#0b1420", "SURFACE": "#111d2c", "SURFACE_2": "#172638",
        "BORDER": "#22374f", "BORDER_STRONG": "#2e4966",
        "INK": "#eafcff", "INK_DIM": "#a9cfd8", "INK_FAINT": "#6f93a0",
        "PINK": "#7cf29a", "CYAN": "#5ad1ff", "YELLOW": "#c38bff",
        "ON_PINK": "#05200d", "ON_CYAN": "#04161f", "ON_YELLOW": "#170826",
    },
    # Reward themes, unlocked by focus hours (focuslock_core.REWARDS).
    "midnight": {
        "BG": "#0d1022", "SURFACE": "#141833", "SURFACE_2": "#1c2144",
        "BORDER": "#2a3060", "BORDER_STRONG": "#3a4280",
        "INK": "#eef0ff", "INK_DIM": "#b3b8de", "INK_FAINT": "#7d83ad",
        "PINK": "#f2b544", "CYAN": "#7aa2ff", "YELLOW": "#ffd98a",
        "ON_PINK": "#1f1503", "ON_CYAN": "#050c24", "ON_YELLOW": "#241a05",
    },
    "sakura": {
        "BG": "#fff4f6", "SURFACE": "#ffffff", "SURFACE_2": "#ffe6ec",
        "BORDER": "#f3c9d4", "BORDER_STRONG": "#e8a8b9",
        "INK": "#3a2630", "INK_DIM": "#6e5260", "INK_FAINT": "#a08592",
        "PINK": "#e0457b", "CYAN": "#2f8a85", "YELLOW": "#a8700a",
        "ON_PINK": "#ffffff", "ON_CYAN": "#ffffff", "ON_YELLOW": "#ffffff",
    },
    "matrix": {
        "BG": "#020804", "SURFACE": "#06120a", "SURFACE_2": "#0b1d10",
        "BORDER": "#133a1d", "BORDER_STRONG": "#1c5a2b",
        "INK": "#b6ffc4", "INK_DIM": "#6fd88a", "INK_FAINT": "#3f8f55",
        "PINK": "#39ff6a", "CYAN": "#00e0a0", "YELLOW": "#d7ff4a",
        "ON_PINK": "#021006", "ON_CYAN": "#021006", "ON_YELLOW": "#021006",
    },
    "mono": {
        "BG": "#111111", "SURFACE": "#1a1a1a", "SURFACE_2": "#262626",
        "BORDER": "#363636", "BORDER_STRONG": "#4a4a4a",
        "INK": "#f5f5f5", "INK_DIM": "#b5b5b5", "INK_FAINT": "#7c7c7c",
        "PINK": "#f5f5f5", "CYAN": "#c4c4c4", "YELLOW": "#e2e2e2",
        "ON_PINK": "#111111", "ON_CYAN": "#111111", "ON_YELLOW": "#111111",
    },
}
THEME_NAMES = [("dark", "Dark"), ("light", "Light"), ("synthwave", "Synthwave"), ("ocean", "Ocean"),
               ("forest", "Forest"), ("paper", "Paper"), ("mono", "Mono"), ("custom", "Custom"),
               ("sunset", "Sunset"), ("gold", "Gold"), ("aurora", "Aurora"),
               ("midnight", "Midnight"), ("sakura", "Sakura"), ("matrix", "Matrix")]
current_theme_name = "dark"

# The "custom" theme: the user picks these six colours in Settings and the
# rest of the palette (borders, dimmed text, text on accents) is derived.
CUSTOM_COLOR_KEYS = [("BG", "Background"), ("SURFACE", "Cards"), ("INK", "Text"),
                     ("PINK", "Accent"), ("CYAN", "Second accent"), ("YELLOW", "Highlight")]
_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def luminance(color):
    """WCAG relative luminance of '#rrggbb'."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = anim.to_rgb(color)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(c1, c2):
    a, b = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def derive_palette(base):
    """A full theme palette from the six user-picked colours."""
    bg, surface, ink = base["BG"], base["SURFACE"], base["INK"]

    def on(accent):   # whichever of near-black / white reads better on the accent
        return "#111111" if contrast(accent, "#111111") >= contrast(accent, "#ffffff") else "#ffffff"
    return {
        "BG": bg, "SURFACE": surface, "SURFACE_2": anim.blend(surface, ink, 0.07),
        "BORDER": anim.blend(surface, ink, 0.17), "BORDER_STRONG": anim.blend(surface, ink, 0.27),
        "INK": ink, "INK_DIM": anim.blend(bg, ink, 0.72), "INK_FAINT": anim.blend(bg, ink, 0.5),
        "PINK": base["PINK"], "CYAN": base["CYAN"], "YELLOW": base["YELLOW"],
        "ON_PINK": on(base["PINK"]), "ON_CYAN": on(base["CYAN"]), "ON_YELLOW": on(base["YELLOW"]),
    }


def default_custom_colors():
    return {key: _THEMES["dark"][key] for key, _ in CUSTOM_COLOR_KEYS}


def load_custom_colors():
    """The saved custom colours, falling back per colour to Dark's for anything missing or invalid."""
    saved = load_settings().get("custom_colors")
    colors = default_custom_colors()
    if isinstance(saved, dict):
        for key, _ in CUSTOM_COLOR_KEYS:
            value = saved.get(key)
            if isinstance(value, str) and _HEX_RE.fullmatch(value):
                colors[key] = value.lower()
    return colors


def set_custom_colors(colors):
    _THEMES["custom"] = derive_palette(colors)


set_custom_colors(default_custom_colors())

# Font presets: each role lists families in order of preference; the first one
# installed wins, and the last entries are common fallbacks so every preset
# still renders on a machine that lacks the headline font.
FONT_PRESETS = {
    "retro": ("Retro", {
        "display": ["Px TandyNew Mono", "DejaVu Sans Mono", "Ubuntu Mono"],
        "mono": ["Ubuntu Mono", "DejaVu Sans Mono", "Liberation Mono"],
        "body": ["Ubuntu", "DejaVu Sans", "Liberation Sans"]}),
    "clean": ("Clean", {
        "display": ["Lato", "Ubuntu Sans", "Noto Sans", "DejaVu Sans"],
        "mono": ["Fira Code", "Ubuntu Sans Mono", "DejaVu Sans Mono", "Liberation Mono"],
        "body": ["Lato", "Ubuntu Sans", "Noto Sans", "DejaVu Sans"]}),
    "modern": ("Modern", {
        "display": ["URW Gothic", "Trebuchet MS", "Verdana", "DejaVu Sans"],
        "mono": ["Ubuntu Sans Mono", "Fira Code", "DejaVu Sans Mono", "Liberation Mono"],
        "body": ["Trebuchet MS", "Verdana", "DejaVu Sans", "Liberation Sans"]}),
    "terminal": ("Terminal", {
        "display": ["IBM 3270", "Fira Code", "DejaVu Sans Mono"],
        "mono": ["Fira Code", "Inconsolata", "DejaVu Sans Mono", "Liberation Mono"],
        "body": ["Fira Code", "Inconsolata", "DejaVu Sans Mono", "Liberation Mono"]}),
    "classic": ("Classic", {
        "display": ["Georgia", "DejaVu Serif", "Noto Serif", "Liberation Serif"],
        "mono": ["Courier New", "Liberation Mono", "Nimbus Mono PS", "DejaVu Sans Mono"],
        "body": ["Georgia", "Noto Serif", "DejaVu Serif", "Liberation Serif"]}),
    "typewriter": ("Typewriter", {
        "display": ["Special Elite", "Courier New", "Nimbus Mono PS", "DejaVu Sans Mono"],
        "mono": ["Courier New", "Nimbus Mono PS", "Liberation Mono", "DejaVu Sans Mono"],
        "body": ["Courier New", "Nimbus Mono PS", "Liberation Mono", "DejaVu Sans Mono"]}),
    # Reward presets, unlocked by focus hours (focuslock_core.REWARDS).
    "commodore": ("Commodore", {
        "display": ["C-64", "Px TandyNew Mono", "DejaVu Sans Mono"],
        "mono": ["C-64", "Ubuntu Mono", "DejaVu Sans Mono"],
        "body": ["Ubuntu", "DejaVu Sans", "Liberation Sans"]}),
    "amiga": ("Amiga", {
        "display": ["Amiga", "Px TandyNew Mono", "DejaVu Sans Mono"],
        "mono": ["Amiga", "Ubuntu Mono", "DejaVu Sans Mono"],
        "body": ["Ubuntu", "DejaVu Sans", "Liberation Sans"]}),
    "ocr": ("OCR", {
        "display": ["OCR A", "DejaVu Sans Mono"],
        "mono": ["OCR A", "DejaVu Sans Mono", "Liberation Mono"],
        "body": ["DejaVu Sans", "Ubuntu", "Liberation Sans"]}),
    "arcade": ("Arcade", {
        "display": ["Px IBM VGA9", "Px IBM VGA8", "Px TandyNew Mono", "DejaVu Sans Mono"],
        "mono": ["Px IBM VGA9", "Px IBM VGA8", "Ubuntu Mono", "DejaVu Sans Mono"],
        "body": ["Ubuntu Mono", "DejaVu Sans Mono", "Liberation Mono"]}),
}
current_font_preset = "retro"

TEXT_SIZES = [("small", "Small", 0.9), ("default", "Default", 1.0), ("large", "Large", 1.15),
              ("xl", "Extra large", 1.3)]
TEXT_SCALE = 1.0
current_text_size = "default"


def apply_text_size(key):
    global TEXT_SCALE, current_text_size
    scales = {k: v for k, _, v in TEXT_SIZES}
    current_text_size = key if key in scales else "default"
    TEXT_SCALE = scales[current_text_size]


def apply_font_preset(key):
    global current_font_preset
    current_font_preset = key if key in FONT_PRESETS else "retro"


def apply_theme(name):
    global current_theme_name, BG, SURFACE, SURFACE_2, BORDER, BORDER_STRONG
    global INK, INK_DIM, INK_FAINT, PINK, CYAN, YELLOW, ON_PINK, ON_CYAN, ON_YELLOW
    global PINK_HOVER, CYAN_HOVER
    current_theme_name = name
    t = _THEMES[name]
    BG, SURFACE, SURFACE_2 = t["BG"], t["SURFACE"], t["SURFACE_2"]
    BORDER, BORDER_STRONG = t["BORDER"], t["BORDER_STRONG"]
    INK, INK_DIM, INK_FAINT = t["INK"], t["INK_DIM"], t["INK_FAINT"]
    PINK, CYAN, YELLOW = t["PINK"], t["CYAN"], t["YELLOW"]
    ON_PINK, ON_CYAN, ON_YELLOW = t["ON_PINK"], t["ON_CYAN"], t["ON_YELLOW"]
    PINK_HOVER, CYAN_HOVER = anim.lighten(PINK, 0.22), anim.lighten(CYAN, 0.25)


apply_theme("dark")

# Short lines rotated under the countdown while locked.
FOCUS_TIPS = [
    "The urge to check something usually fades in about ten minutes. Outlast it.",
    "Stuck? Make the next step smaller, then do just that.",
    "You already made the decision. Now it's just following through.",
    "Write the distraction down, then get back to the task.",
    "Boring progress is still progress.",
    "Past you set this lock for a reason. Trust them.",
    "Drink some water, stretch, then one more task.",
    "Finish one thing before starting the next.",
]


_font_families = None


def _pick_font(candidates, size, weight="normal"):
    # families() is slow (it lists every installed font) and fonts are picked
    # on every frame of some animations, so look it up once.
    global _font_families
    size = max(5, round(size * TEXT_SCALE)) if size > 0 else size   # the Text size setting
    if _font_families is None:
        try:
            _font_families = set(tkfont.families())
        except tk.TclError:
            return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)
    available = _font_families
    for name in candidates:
        if name in available:
            return (name, size, weight) if weight != "normal" else (name, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


# Tried after a preset's own list, so Windows (which has none of the Linux
# fonts above) still gets a monospace font where one is meant.
FALLBACK_FONTS = {"display": ["Consolas"], "mono": ["Consolas", "Courier New"], "body": ["Segoe UI"]}


def preset_font(preset, role, size, weight="normal"):
    """A font for one role ("display", "mono" or "body") of a font preset."""
    return _pick_font(FONT_PRESETS[preset][1][role] + FALLBACK_FONTS[role], size, weight)


def display_font(size, weight="normal"):
    return preset_font(current_font_preset, "display", size, weight)


def mono_font(size, weight="normal"):
    return preset_font(current_font_preset, "mono", size, weight)


def body_font(size, weight="normal"):
    return preset_font(current_font_preset, "body", size, weight)


def text_width(text, font):
    return tkfont.Font(font=font).measure(text)


def hint_floating(window, wtype="dialog"):
    """Ask the window manager to float this window instead of tiling it, via
    the standard EWMH _NET_WM_WINDOW_TYPE hint (X11/XWayland only). This is
    portable across window managers (Hyprland, i3, GNOME, KDE, ...) and
    needs no WM-specific config -- most tiling WMs auto-float "dialog" and
    "utility" typed windows by convention. Silently does nothing if the Tk
    build/platform doesn't support the -type attribute."""
    try:
        window.attributes("-type", wtype)
    except tk.TclError:
        pass


def fmt_date(when, fmt):
    """strftime, plus %-d (day without a leading zero), which Windows' C
    library rejects."""
    return when.strftime(fmt.replace("%-d", str(when.day)))


def raise_window(widget):
    # Canvas overrides lift()/tkraise() to mean "raise canvas items", so go
    # through Misc to restack the widget itself.
    tk.Misc.tkraise(widget)


def is_inside(widget, x_root, y_root):
    """True if the screen point is over widget or one of its descendants."""
    try:
        under = widget.winfo_containing(x_root, y_root)
    except (tk.TclError, KeyError):
        return False
    return under is not None and str(under).startswith(str(widget))


def _pad_total(widget):
    try:
        info = widget.pack_info()
    except tk.TclError:
        try:
            info = widget.grid_info()
        except tk.TclError:
            return 0
    padx = info.get("padx", 0)
    if isinstance(padx, (tuple, list)):
        return sum(int(p) for p in padx)
    if isinstance(padx, str) and " " in padx:
        return sum(int(p) for p in padx.split())
    return 2 * int(padx or 0)


def responsive_wraps(root, min_wrap=150):
    """Labels are given a fixed wraplength when built; in a narrow window
    that can be wider than the space they get, and Tk then clips the text on
    both sides. Cap every wrapped label to its container's actual width,
    updating as the window resizes."""
    for w in anim.walk(root):
        if not isinstance(w, tk.Label):
            continue
        try:
            wanted = int(float(str(w.cget("wraplength"))))
        except (tk.TclError, ValueError):
            continue
        if wanted < 200 or getattr(w, "_wrap_wanted", None):
            continue
        w._wrap_wanted = wanted
        master = w.master

        def fit(_event=None, label=w, master=master):
            if not anim._alive(label):
                return
            avail = master.winfo_width() - _pad_total(label) - 6
            if avail > 1:
                label.configure(wraplength=max(min_wrap, min(label._wrap_wanted, avail)))
        master.bind("<Configure>", fit, add="+")
        fit()


def stagger_in(widgets, step=70, duration=380, start=0, from_color=None):
    for i, w in enumerate(widgets):
        anim.fade_in(w, from_color or BG, duration, delay_ms=start + i * step)


def format_hours(secs):
    """Hours and minutes, never days: 82h 05m."""
    h, m = divmod(int(secs) // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def format_minutes(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m}m")


def format_span(secs, with_seconds=True):
    d, rem = divmod(max(0, int(secs)), 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if with_seconds:
        return f"{d}d {h:02d}h {m:02d}m {s:02d}s" if d else f"{h:02d}h {m:02d}m {s:02d}s"
    parts = [f"{d}d"] if d else []
    if h or d:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


# ---------- widgets ----------

def rounded_rect_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class PillButton(tk.Canvas):
    """Rounded-rect button: eased hover colour, a press 'squish', and the
    command fires on release (only if the pointer is still over it), like a
    native button. Optional breathe() adds a slow idle glow."""

    def __init__(self, parent, text, command=None, bg=None, fg=None,
                 hover_bg=None, font=None, width=200, height=40, radius=None, sound="click"):
        self.parent_bg = parent["bg"] if "bg" in parent.keys() else BG
        self.sound = sound
        font = font or mono_font(11, "bold")
        width = max(width, text_width(text, font) + 24)   # never clip the label (e.g. at a large text size)
        super().__init__(parent, width=width, height=height, bg=self.parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.font = font
        self.radius = radius if radius is not None else height // 2
        self.label = text
        self.set_colors(bg or PINK, fg or ON_PINK, hover_bg, redraw=False)
        self._enabled = True
        self._hover = 0.0
        self._pressed = False
        self._fade = 1.0
        self._breath = 0.0
        self._hover_anim = None
        self._draw()
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: self._tween_hover(1.0))
        self.bind("<Leave>", self._on_leave)

    def set_colors(self, bg, fg, hover_bg=None, redraw=True):
        self.bg_color = bg
        self.fg_color = fg
        self.hover_bg = hover_bg or anim.lighten(bg, 0.12)
        if redraw:
            self._draw()

    def _draw(self):
        w, h = int(self["width"]), int(self["height"])
        if self._enabled:
            fill = anim.blend(self.bg_color, self.hover_bg, self._hover)
            if self._breath:
                fill = anim.blend(fill, anim.lighten(self.bg_color, 0.3), self._breath * (1 - self._hover))
            ink = self.fg_color
        else:
            fill, ink = BORDER, INK_FAINT
        fill = anim.blend(BG, fill, self._fade)
        ink = anim.blend(BG, ink, self._fade)
        inset = 2.5 if self._pressed else 0.5
        self.delete("all")
        self.create_polygon(rounded_rect_points(inset, inset, w - inset, h - inset, self.radius - inset),
                            smooth=True, fill=fill, outline="")
        self.create_text(w / 2, h / 2 + (1 if self._pressed else 0), text=self.label, fill=ink, font=self.font)

    def _tween_hover(self, target):
        if not self._enabled:
            return
        if self._hover_anim:
            self._hover_anim.cancel()
        start = self._hover

        def frame(t):
            self._hover = start + (target - start) * t
            self._draw()
        self._hover_anim = anim.animate(self, 150, frame)

    def _on_leave(self, _event):
        self._pressed = False
        self._tween_hover(0.0)

    def _on_press(self, _event):
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, event):
        was_pressed, self._pressed = self._pressed, False
        if not self._enabled:
            return
        self._draw()
        inside = 0 <= event.x < int(self["width"]) and 0 <= event.y < int(self["height"])
        if was_pressed and inside and self.command:
            if self.sound:
                snd.play(self.sound)
            self.command()  # may destroy this widget; nothing after this line

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def breathe(self, period_ms=2800, depth=0.35):
        def frame(phase):
            self._breath = depth * (1 - math.cos(2 * math.pi * phase)) / 2
            if self._hover < 1.0:
                self._draw()
        return anim.loop(self, period_ms, frame)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self._hover = 0.0
        self.config(cursor="hand2" if enabled else "arrow")
        self._draw()


def make_pill(parent, text, command, bg=None, fg=None, hover_bg=None,
              font=None, width=220, height=44, radius=None):
    return PillButton(parent, text, command, bg=bg, fg=fg, hover_bg=hover_bg,
                      font=font, width=width, height=height, radius=radius)


def small_pill(parent, text, command, width=None, height=32, font=None, **kw):
    font = font or mono_font(9)
    width = width or text_width(text, font) + 30
    kw.setdefault("bg", SURFACE_2)
    kw.setdefault("fg", INK_DIM)
    kw.setdefault("hover_bg", BORDER)
    return PillButton(parent, text, command, font=font, width=width, height=height,
                      radius=height // 2, **kw)


class ToggleSwitch(tk.Canvas):
    """A labelled on/off switch bound to a BooleanVar. The knob springs
    across (slightly overshooting) whenever the variable changes -- whether
    from a click, a preset, or Select all -- because it animates off the
    variable's trace rather than the click."""

    TRACK_W, TRACK_H = 38, 20

    def __init__(self, parent, text, variable, width=250, accent=None, font=None):
        parent_bg = parent["bg"] if "bg" in parent.keys() else BG
        super().__init__(parent, width=width, height=30, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.var = variable
        self.text = text
        self.accent = accent or PINK
        self.font = font or body_font(11)
        self._pos = 1.0 if variable.get() else 0.0
        self._hover = 0.0
        self._fade = 1.0
        self._anim = None
        self._hover_anim = None
        self._trace = variable.trace_add("write", self._on_var)
        self.bind("<Destroy>", self._on_destroy)
        self.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._tween_hover(1.0))
        self.bind("<Leave>", lambda e: self._tween_hover(0.0))
        self._draw()

    def _on_destroy(self, event):
        if event.widget is self:
            try:
                self.var.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass

    def _on_click(self, event):
        if 0 <= event.x < int(self["width"]) and 0 <= event.y < int(self["height"]):
            on = not self.var.get()
            snd.play("toggle_on" if on else "toggle_off")
            self.var.set(on)

    def _on_var(self, *_):
        if not anim._alive(self):
            return
        target = 1.0 if self.var.get() else 0.0
        if self._anim:
            self._anim.cancel()
        start = self._pos

        def frame(t):
            self._pos = start + (target - start) * t
            self._draw()
        self._anim = anim.animate(self, 260, frame, easing=anim.ease_out_back)

    def _tween_hover(self, target):
        if self._hover_anim:
            self._hover_anim.cancel()
        start = self._hover

        def frame(t):
            self._hover = start + (target - start) * t
            self._draw()
        self._hover_anim = anim.animate(self, 140, frame)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        on = max(0.0, min(1.0, self._pos))
        f = self._fade
        tw, th = self.TRACK_W, self.TRACK_H
        x0, y0 = 2, (30 - th) / 2
        track = anim.blend(BORDER, self.accent, on)
        if self._hover:
            track = anim.blend(track, anim.lighten(track, 0.25), self._hover)
        knob = anim.blend(INK_DIM, "#ffffff", on)
        label = anim.blend(INK_DIM, INK, max(on, self._hover))
        self.delete("all")
        self.create_polygon(rounded_rect_points(x0, y0, x0 + tw, y0 + th, th / 2), smooth=True,
                            fill=anim.blend(BG, track, f), outline="")
        r = th / 2 - 3
        kx = x0 + th / 2 + self._pos * (tw - th)
        ky = y0 + th / 2
        self.create_oval(kx - r, ky - r, kx + r, ky + r, fill=anim.blend(BG, knob, f), outline="")
        self.create_text(x0 + tw + 12, 15, text=self.text, anchor="w",
                         fill=anim.blend(BG, label, f), font=self.font)


class Chip(tk.Canvas):
    """A small rounded tag (e.g. one blocked app). pop() scales it in."""

    def __init__(self, parent, text, accent, font=None):
        self.font = font or body_font(10)
        self.text = text
        self.accent = accent
        w = text_width(text, self.font) + 40
        super().__init__(parent, width=w, height=34, bg=parent["bg"], highlightthickness=0, bd=0)
        self._grow = 1.0
        self._fade = 1.0
        self._hover = 0.0
        self.bind("<Enter>", lambda e: self._set_hover(1.0))
        self.bind("<Leave>", lambda e: self._set_hover(0.0))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def pop(self, delay_ms=0):
        self._grow = 0.0
        self._draw()

        def frame(t):
            self._grow = t
            self._draw()
        return anim.animate(self, 380, frame, easing=anim.ease_out_back, delay_ms=delay_ms)

    def _draw(self):
        w, h = int(self["width"]), int(self["height"])
        g = self._grow
        inset_x = (1 - g) * w / 2 + 3
        inset_y = (1 - g) * h / 2 + 3
        self.delete("all")
        if g <= 0.02:
            return
        x1, y1, x2, y2 = inset_x, inset_y, w - inset_x, h - inset_y
        if x2 <= x1 or y2 <= y1:
            return
        f = self._fade * min(1.0, g * 1.5)
        outline = anim.blend(self.accent, anim.lighten(self.accent, 0.3), self._hover)
        self.create_polygon(rounded_rect_points(x1, y1, x2, y2, (y2 - y1) / 2), smooth=True,
                            fill=anim.blend(BG, SURFACE_2, f), outline=anim.blend(BG, outline, f), width=1.5)
        if g > 0.6:
            cy = h / 2
            self.create_oval(x1 + 10, cy - 3.5, x1 + 17, cy + 3.5, fill=anim.blend(BG, self.accent, f), outline="")
            self.create_text(x1 + 24, cy, text=self.text, anchor="w", font=self.font, fill=anim.blend(BG, INK, f))


class FlowFrame(tk.Frame):
    """Lays its items out left-to-right, wrapping onto new rows to fit the
    available width (Tk has no built-in flow layout)."""

    def __init__(self, parent, bg, gap=8):
        super().__init__(parent, bg=bg, height=1)
        self.gap = gap
        self.items = []
        self.bind("<Configure>", self._relayout)

    def add(self, widget):
        self.items.append(widget)
        self._relayout()

    def _relayout(self, _event=None):
        width = self.winfo_width()
        if width <= 1:
            return
        x = y = row_h = 0
        for w in self.items:
            ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
            if x > 0 and x + ww > width:
                x, y, row_h = 0, y + row_h + self.gap, 0
            w.place(x=x, y=y)
            x += ww + self.gap
            row_h = max(row_h, wh)
        if int(self["height"]) != y + row_h:
            self.configure(height=max(1, y + row_h))


def card_frame(parent, bg=None, hover=True):
    """A Frame with a 1px border; the border eases toward the accent colour
    while the pointer is over the card."""
    card = tk.Frame(parent, bg=bg or SURFACE, highlightbackground=BORDER, highlightthickness=1, bd=0)
    if not hover:
        return card
    state = {"t": 0.0, "anim": None}
    glow = anim.blend(BORDER, PINK, 0.55)

    def tween(target):
        if state["anim"]:
            state["anim"].cancel()
        start = state["t"]

        def frame(t):
            state["t"] = start + (target - start) * t
            card.configure(highlightbackground=anim.blend(BORDER, glow, state["t"]))
        state["anim"] = anim.animate(card, 220, frame)

    def on_leave(event):
        # Moving onto a child widget also sends <Leave>; only fade out once
        # the pointer has really left the card.
        if not is_inside(card, event.x_root, event.y_root):
            tween(0.0)

    card.bind("<Enter>", lambda e: tween(1.0))
    card.bind("<Leave>", on_leave)
    return card


def card_title(card, text, color=None):
    tk.Label(card, text=text, font=mono_font(10, "bold"), bg=card["bg"], fg=color or CYAN).pack(
        anchor="w", padx=16, pady=(14, 8)
    )


class ScrollableFrame(tk.Frame):
    """A vertically scrollable content area with eased wheel scrolling.
    Put widgets in .inner; the owner routes wheel events to scroll_by()."""

    STEP_PX = 90

    def __init__(self, parent, bg=None):
        bg = bg or BG
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._scroll_anim = None
        self._target = None

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def scroll_by(self, notches):
        bbox = self.canvas.bbox("all")
        total = (bbox[3] - bbox[1]) if bbox else 0
        view = self.canvas.winfo_height()
        if total <= view:
            return
        max_top = 1.0 - view / total
        current = self.canvas.yview()[0]
        base = self._target if self._target is not None else current
        target = max(0.0, min(max_top, base + notches * self.STEP_PX / total))
        self._target = target
        if self._scroll_anim:
            self._scroll_anim.cancel()

        def frame(t):
            self.canvas.yview_moveto(current + (target - current) * t)

        def done():
            self._target = None
        self._scroll_anim = anim.animate(self.canvas, 240, frame, on_done=done)


def draw_padlock(canvas, cx, cy, lift=0.0, scale=1.0, body=None, shackle=None, hole=None, tag="lock"):
    """A padlock centred on (cx, cy). lift > 0 raises the shackle (open)."""
    s = scale
    bw, bh = 84 * s, 64 * s
    top = cy - bh / 2 + 10 * s
    r = 25 * s
    sy = top - lift * s
    leg = 8 * s
    pts = [cx - r, sy + leg + 14 * s, cx - r, sy]
    for i in range(1, 16):
        a = math.pi - math.pi * i / 16
        pts += [cx + r * math.cos(a), sy - r * math.sin(a)]
    pts += [cx + r, sy, cx + r, sy + leg + 14 * s]
    canvas.create_line(*pts, width=10 * s, fill=shackle or INK_DIM, capstyle="round",
                       joinstyle="round", smooth=True, tags=tag)
    canvas.create_polygon(rounded_rect_points(cx - bw / 2, top, cx + bw / 2, top + bh, 14 * s),
                          smooth=True, fill=body or PINK, outline="", tags=tag)
    ky = top + bh * 0.42
    canvas.create_oval(cx - 7 * s, ky - 7 * s, cx + 7 * s, ky + 7 * s, fill=hole or ON_PINK, outline="", tags=tag)
    canvas.create_polygon(cx - 4 * s, ky + 2 * s, cx + 4 * s, ky + 2 * s, cx + 2.5 * s, ky + 17 * s,
                          cx - 2.5 * s, ky + 17 * s, fill=hole or ON_PINK, outline="", tags=tag)


class LockBadge(tk.Canvas):
    """The locked view's padlock: shackle drops shut with a bounce, the body
    flashes on impact, then sonar rings pulse out from it forever."""

    W, H = 260, 220

    def __init__(self, parent, intro=True):
        super().__init__(parent, width=self.W, height=self.H, bg=parent["bg"], highlightthickness=0, bd=0)
        self.lift_px = 30.0 if intro else 0.0
        self.flash = 0.0
        self.phase = None
        self._fade = 1.0
        self._draw()
        if intro:
            anim.animate(self, 750, self._drop, easing=anim.ease_out_bounce, delay_ms=350,
                         on_done=self._impact)
            anim.loop(self, 2600, self._ping, delay_ms=1300)
        else:
            anim.loop(self, 2600, self._ping)

    def _drop(self, t):
        self.lift_px = 30.0 * (1 - t)
        self._draw()

    def _impact(self):
        def frame(t):
            self.flash = 1 - t
            self._draw()
        anim.animate(self, 500, frame)

    def _ping(self, phase):
        self.phase = phase
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        # Body centre sits at (cx, cy + 10); rings reach 94px from it.
        cx, cy = self.W / 2, 100
        bg = self["bg"]
        self.delete("all")
        if self.phase is not None:
            for offset in (0.0, 0.5):
                p = (self.phase + offset) % 1.0
                rad = 44 + 50 * p
                color = anim.blend(PINK, bg, anim.ease_out_cubic(p))
                self.create_oval(cx - rad, cy - rad + 10, cx + rad, cy + rad + 10, outline=color, width=2)
        body = anim.blend(PINK, "#ffffff", self.flash * 0.5)
        f = self._fade
        draw_padlock(self, cx, cy, lift=self.lift_px,
                     body=anim.blend(BG, body, f), shackle=anim.blend(BG, INK_DIM, f),
                     hole=anim.blend(BG, ON_PINK, f))


class ProgressBar(tk.Canvas):
    """Rounded progress bar with a highlight that sweeps across the filled part."""

    H = 14

    def __init__(self, parent, fraction):
        super().__init__(parent, height=self.H, bg=parent["bg"], highlightthickness=0, bd=0)
        self.fraction = 0.0
        self.shimmer = None
        self._fade = 1.0
        self._grow_anim = None
        self.bind("<Configure>", lambda e: self._draw())
        self.set_fraction(fraction, duration=1100, delay=500)
        anim.loop(self, 2400, self._shimmer, delay_ms=1600)

    def set_fraction(self, fraction, duration=600, delay=0):
        fraction = max(0.0, min(1.0, fraction))
        if self._grow_anim:
            self._grow_anim.cancel()
        start = self.fraction

        def frame(t):
            self.fraction = start + (fraction - start) * t
            self._draw()
        self._grow_anim = anim.animate(self, duration, frame, easing=anim.ease_in_out_cubic, delay_ms=delay)

    def _shimmer(self, phase):
        self.shimmer = phase
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        w, h = self.winfo_width(), self.H
        if w <= 1:
            return
        f = self._fade
        self.delete("all")
        self.create_polygon(rounded_rect_points(0, 0, w, h, h / 2), smooth=True,
                            fill=anim.blend(BG, SURFACE_2, f), outline="")
        fill_w = max(h, w * self.fraction) if self.fraction > 0 else 0
        if not fill_w:
            return
        self.create_polygon(rounded_rect_points(0, 0, fill_w, h, h / 2), smooth=True,
                            fill=anim.blend(BG, PINK, f), outline="")
        if self.shimmer is None or fill_w < h * 2:
            return
        # A soft band (three stepped strips) sliding left to right, kept
        # clear of the rounded ends so it never pokes outside the bar.
        band_c = -60 + (fill_w + 120) * self.shimmer
        for half_w, amount in ((30, 0.12), (18, 0.22), (7, 0.34)):
            x1 = max(h / 2, band_c - half_w)
            x2 = min(fill_w - h / 2, band_c + half_w)
            if x2 > x1:
                self.create_rectangle(x1, 2, x2, h - 2, outline="",
                                      fill=anim.blend(BG, anim.lighten(PINK, amount), f))


class Heatmap(tk.Canvas):
    """The activity calendar. Cells ripple in diagonally, and hovering a
    cell reports its date through on_hover(text)."""

    WEEKS, CELL, GAP = 18, 14, 3

    def __init__(self, parent, locked_days, on_hover=None, intro=True):
        weeks, cell, gap = self.WEEKS, self.CELL, self.GAP
        super().__init__(parent, width=weeks * (cell + gap) + gap, height=7 * (cell + gap) + gap,
                         bg=parent["bg"], highlightthickness=0)
        self.on_hover = on_hover
        today = date.today()
        # Snap the END forward to the coming Sunday (not the start backward
        # to Monday) so the range is always exactly weeks*7 days -- snapping
        # the start backward instead can overshoot by a few days depending
        # on today's weekday, drawing cells past the canvas's right edge.
        week_end = today + timedelta(days=6 - today.weekday())
        self.range_start = week_end - timedelta(days=weeks * 7 - 1)
        self.cells = []  # (item, col, row, day)
        d, col = self.range_start, 0
        while d <= week_end:
            row = d.weekday()
            locked = d in locked_days and d <= today
            fill = PINK if locked else SURFACE_2
            outline = YELLOW if d == today else BORDER
            item = self.create_rectangle(0, 0, 0, 0, fill=fill, outline=outline, width=2 if d == today else 1)
            self.cells.append((item, col, row, d))
            if row == 6:
                col += 1
            d += timedelta(days=1)
        self.locked_days = locked_days
        self.today = today
        if intro:
            self._layout(0.0)
            anim.animate(self, 1100, self._layout, easing=anim.linear, delay_ms=250)
        else:
            self._layout(1.0)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: on_hover and on_hover(None))

    def _layout(self, t):
        cell, gap = self.CELL, self.GAP
        span = self.WEEKS + 7  # diagonal index range
        for item, col, row, _ in self.cells:
            # Each cell starts a little after its up-left neighbour.
            local = t * 1.6 - 0.6 * (col + row) / span
            k = anim.ease_out_back(max(0.0, min(1.0, local * 2.2)))
            half = cell / 2 * k
            x = gap + col * (cell + gap) + cell / 2
            y = gap + row * (cell + gap) + cell / 2
            self.coords(item, x - half, y - half, x + half, y + half)

    def _on_motion(self, event):
        if not self.on_hover:
            return
        step = self.CELL + self.GAP
        col, row = (event.x - self.GAP) // step, (event.y - self.GAP) // step
        if not (0 <= col < self.WEEKS and 0 <= row < 7):
            self.on_hover(None)
            return
        d = self.range_start + timedelta(days=col * 7 + row)
        if d > self.today:
            status = "upcoming"
        elif d in self.locked_days:
            status = "locked in ✓"
        else:
            status = "free day"
        label = "Today" if d == self.today else d.strftime("%a %d %b")
        self.on_hover(f"{label}  ·  {status}")


class Toast(tk.Frame):
    """A notification card that slides up from the bottom edge."""

    def __init__(self, root, message, accent, duration_ms):
        super().__init__(root, bg=SURFACE, highlightbackground=accent, highlightthickness=1, bd=0)
        tk.Frame(self, bg=accent, width=5).pack(side="left", fill="y")
        label = tk.Label(self, text=message, bg=SURFACE, fg=INK, font=body_font(10),
                         wraplength=460, justify="left")
        label.pack(side="left", padx=(14, 18), pady=12)
        self.update_idletasks()
        self.h = self.winfo_reqheight()
        self.place(relx=0.5, rely=1.0, anchor="n", y=0)
        raise_window(self)
        self._closing = False
        for w in (self, label):
            w.bind("<Button-1>", lambda e: self.close())

        def frame(t):
            self.place_configure(y=-(self.h + 22) * t)
        anim.animate(self, 420, frame, easing=anim.ease_out_back)
        self._root().after(duration_ms, self.close)

    def close(self):
        if self._closing or not anim._alive(self):
            return
        self._closing = True

        def frame(t):
            self.place_configure(y=-(self.h + 22) * (1 - t))
        anim.animate(self, 260, frame, easing=anim.ease_in_out_cubic, on_done=self.destroy)


def key_sep(keys, i):
    """The joiner drawn before keys[i]: '+' within a combo, 'or' between alternatives."""
    return "or" if keys[i].startswith("|") else "+"


def draw_keycap(canvas, right, y, key, delay=0):
    """Draw a keycap ending at x=right, centred on y; returns its left edge.
    A leading '|' marks an alternative key (shown after 'or')."""
    key = key.lstrip("|")
    font = mono_font(10, "bold")
    w = max(26, text_width(key, font) + 18)
    left = right - w
    cap = canvas.create_polygon(rounded_rect_points(left, y - 13, right, y + 13, 6), smooth=True,
                                fill=BG, outline=BG, width=1)
    label = canvas.create_text(left + w / 2, y, text=key, font=font, fill=BG)

    def fade(t):
        if anim._alive(canvas):
            canvas.itemconfigure(cap, fill=anim.blend(BG, SURFACE_2, t), outline=anim.blend(BG, BORDER_STRONG, t))
            canvas.itemconfigure(label, fill=anim.blend(BG, INK, t))
    anim.animate(canvas, 320, fade, delay_ms=delay)
    return left


class Overlay(tk.Canvas):
    """Full-window layer for privileged work: a spinner while sudo runs,
    then either a celebration (padlock snaps shut + confetti) or a quick
    exit on failure. Slides up off the window to reveal what's beneath."""

    def __init__(self, root):
        super().__init__(root, bg=BG, highlightthickness=0, bd=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        raise_window(self)
        self._spin = None
        self._leaving = False
        self.update_idletasks()

    def _center(self):
        return self.winfo_width() / 2, self.winfo_height() / 2 - 30

    def working(self, text):
        self._text = text
        self._spin = anim.loop(self, 1500, self._draw_spinner)

    def _draw_spinner(self, phase):
        cx, cy = self._center()
        self.delete("spin")
        for r, color, speed, extent in ((48, PINK, 1, 110), (35, CYAN, -2, 90), (22, YELLOW, 3, 70)):
            start = (phase * 360 * speed) % 360
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=extent,
                            style="arc", outline=color, width=5, tags="spin")
        dots = "." * int(phase * 4)
        self.create_text(cx, cy + 86, text=f"{self._text}{dots:<3}", fill=INK_DIM,
                         font=mono_font(12, "bold"), tags="spin")

    def effect(self, style, cx, cy):
        """The burst when the padlock snaps shut: classic confetti, or a
        celebration style unlocked by focus hours."""
        colors = [PINK, CYAN, YELLOW, INK]
        w, h = self.winfo_width(), self.winfo_height()
        if style == "fireworks":
            for i in range(6):
                bx, by = random.uniform(w * 0.15, w * 0.85), random.uniform(h * 0.12, h * 0.45)
                self._root().after(i * 260, lambda bx=bx, by=by, c=random.choice(colors):
                                   anim._alive(self) and self._burst(bx, by, c, 34, 160, 1300, gravity=90))
                self._root().after(i * 260, lambda: snd.play("click"))
        elif style == "starfall":
            for i in range(55):
                self._root().after(int(i * 35), lambda: anim._alive(self) and self._falling_star(w, h, colors))
        elif style == "supernova":
            flash = self.create_rectangle(0, 0, w, h, fill=INK, outline="")
            anim.animate(self, 500, lambda t: anim._alive(self) and self.itemconfigure(
                flash, fill=anim.blend(INK, BG, t)), on_done=lambda: anim._alive(self) and self.delete(flash))
            self.tag_lower(flash)
            for k, color in enumerate((YELLOW, PINK, CYAN)):
                ring = self.create_oval(cx, cy, cx, cy, outline=color, width=6 - k)

                def grow(t, ring=ring, color=color, k=k):
                    rad = 30 + (max(w, h) * 0.75) * t
                    self.coords(ring, cx - rad, cy - rad, cx + rad, cy + rad)
                    self.itemconfigure(ring, outline=anim.blend(color, BG, t))
                anim.animate(self, 1300 + k * 250, grow, easing=anim.ease_out_cubic, delay_ms=k * 120,
                             on_done=lambda ring=ring: anim._alive(self) and self.delete(ring))
            self._burst(cx, cy, YELLOW, 70, 420, 1500)
            self._burst(cx, cy, PINK, 50, 300, 1400)
        anim.confetti(self, cx, cy - 10, colors, fade_to=BG, count=90 if style == "classic" else 30)

    def _burst(self, x, y, color, count, speed, ms, gravity=0.0):
        """Particles flying out from (x, y), fading as they go."""
        parts = []
        for i in range(count):
            ang = 2 * math.pi * i / count + random.uniform(-0.08, 0.08)
            v = speed * random.uniform(0.6, 1.0)
            dot = self.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline="")
            parts.append((dot, math.cos(ang) * v, math.sin(ang) * v))

        def frame(t):
            secs = t * ms / 1000
            for dot, vx, vy in parts:
                px, py = x + vx * secs, y + vy * secs + gravity * secs * secs
                r = 2.6 * (1 - t) + 0.6
                self.coords(dot, px - r, py - r, px + r, py + r)
                self.itemconfigure(dot, fill=anim.blend(color, BG, t ** 1.5))
        anim.animate(self, ms, frame, easing=anim.linear,
                     on_done=lambda: anim._alive(self) and [self.delete(d) for d, _, _ in parts])

    def _falling_star(self, w, h, colors):
        x0, size = random.uniform(0, w), random.uniform(5, 11)
        color = random.choice(colors)
        star = self.create_polygon(0, 0, 0, 0, fill=color, outline="")
        drift, spin = random.uniform(-60, 60), random.uniform(-4, 4)

        def frame(t):
            y = -20 + (h + 40) * t
            x = x0 + drift * t
            pts = []
            for i in range(10):
                rad = size if i % 2 == 0 else size * 0.45
                a = spin * t + i * math.pi / 5 - math.pi / 2
                pts += [x + rad * math.cos(a), y + rad * math.sin(a)]
            self.coords(star, *pts)
            self.itemconfigure(star, fill=anim.blend(color, BG, max(0.0, t - 0.6) / 0.4))
        anim.animate(self, int(random.uniform(1300, 2100)), frame, easing=anim.linear,
                     on_done=lambda: anim._alive(self) and self.delete(star))

    def celebrate(self, title, lines, on_reveal, hold_ms=2600, style="classic"):
        if self._spin:
            self._spin.cancel()
        self.delete("all")
        cx, cy = self._center()
        state = {"lift": 34.0, "flash": 0.0}

        def draw_lock():
            self.delete("lock")
            draw_padlock(self, cx, cy, lift=state["lift"], scale=1.25,
                         body=anim.blend(PINK, "#ffffff", state["flash"] * 0.6))
            self.tag_lower("lock")  # keep confetti in front

        def drop(t):
            state["lift"] = 34.0 * (1 - t)
            draw_lock()

        def impact():
            snd.play("lock")
            self.effect(style, cx, cy)
            ring = self.create_oval(cx, cy, cx, cy, outline=PINK, width=3)

            def ring_frame(t):
                rad = 50 + 150 * t
                self.coords(ring, cx - rad, cy - rad, cx + rad, cy + rad)
                self.itemconfigure(ring, outline=anim.blend(PINK, BG, t))
                state["flash"] = max(0.0, 1 - t * 2)
                draw_lock()
            anim.animate(self, 650, ring_frame, on_done=lambda: self.delete(ring))
            show_text()

        def show_text():
            head = self.create_text(cx, cy + 110, text=title, fill=YELLOW, font=display_font(10, "bold"))

            def grow(t):
                self.itemconfigure(head, font=display_font(max(1, int(10 + 22 * t)), "bold"))
            anim.animate(self, 450, grow, easing=anim.ease_out_back)
            for i, line in enumerate(lines):
                item = self.create_text(cx, cy + 156 + i * 24, text=line, fill=BG, font=body_font(11))

                def fade(t, item=item):
                    self.itemconfigure(item, fill=anim.blend(BG, INK_DIM, t))
                anim.animate(self, 400, fade, delay_ms=250 + i * 120)

        draw_lock()
        anim.animate(self, 700, drop, easing=anim.ease_out_bounce, delay_ms=150, on_done=impact)
        self.bind("<Button-1>", lambda e: self.leave(on_reveal))
        self._root().after(hold_ms, lambda: self.leave(on_reveal))

    def badges(self, badges, on_done):
        """Present newly earned badges one at a time: rays turn behind the
        medal as it bounces in, then confetti. Click (or wait) for the next."""
        if self._spin:
            self._spin.cancel()
        queue = list(badges)
        total = len(queue)
        state = {"token": 0, "loop": None}

        def show(badge):
            state["token"] += 1
            token = state["token"]
            if state["loop"]:
                state["loop"].cancel()
            self.delete("all")
            cx, cy = self._center()
            cy -= 10
            fill, _ = accent_colors(badge["accent"])
            ray_color = anim.blend(fill, BG, 0.82)
            g = {"s": 0.0}

            def draw(phase):
                self.delete("medal")
                for i in range(12):
                    a = math.radians(phase * 360 + i * 30)
                    da = math.radians(5)
                    self.create_polygon(cx, cy, cx + 230 * math.cos(a - da), cy + 230 * math.sin(a - da),
                                        cx + 230 * math.cos(a + da), cy + 230 * math.sin(a + da),
                                        fill=ray_color, outline="", tags="medal")
                if g["s"] > 0.02:
                    draw_medal(self, cx, cy, 1.9 * g["s"], badge, tag="medal")
                self.tag_lower("medal")  # keep text and confetti on top
            state["loop"] = anim.loop(self, 12000, draw)
            anim.animate(self, 750, lambda t: g.__setitem__("s", t), easing=anim.ease_out_back, delay_ms=120)
            snd.play("badge")

            def burst():
                if token == state["token"] and anim._alive(self):
                    anim.confetti(self, cx, cy - 20, [fill, PINK, CYAN, YELLOW], fade_to=BG, count=70)
            self._root().after(350, burst)

            self.create_text(cx, cy - 135, text="BADGE UNLOCKED", fill=YELLOW, font=mono_font(12, "bold"))
            self.create_text(cx, cy + 120, text=badge["name"], fill=INK, font=display_font(24, "bold"))
            self.create_text(cx, cy + 158, text=badge["desc"], fill=INK_DIM, font=body_font(11))
            done_n = total - len(queue)
            footer = f"{done_n} of {total}  ·  click to continue" if total > 1 else "click to continue"
            self.create_text(cx, cy + 196, text=footer, fill=INK_FAINT, font=mono_font(9))
            self._root().after(4200, lambda: advance(token))

        def advance(token=None):
            if token is not None and token != state["token"]:
                return  # the user already clicked past this one
            if not anim._alive(self) or self._leaving:
                return
            if queue:
                show(queue.pop(0))
            else:
                if state["loop"]:
                    state["loop"].cancel()
                self.leave(on_done)

        self.bind("<Button-1>", lambda e: advance())
        advance()

    def recap(self, data, stats, on_done):
        """The weekly recap: a one-screen, animated summary of a week."""
        if self._spin:
            self._spin.cancel()
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        cx = w / 2
        y0 = max(30, (h - 700) / 2)

        def fade_item(item, color, delay, duration=380):
            self.itemconfigure(item, fill=BG)
            anim.animate(self, duration, lambda t: self.itemconfigure(item, fill=anim.blend(BG, color, t)),
                         delay_ms=delay)

        ws = data["week_start"]
        we = ws + timedelta(days=6)
        span = (f"{ws.day} \u2013 {we.day} {we.strftime('%b').upper()}" if ws.month == we.month
                else f"{ws.day} {ws.strftime('%b').upper()} \u2013 {we.day} {we.strftime('%b').upper()}")
        fade_item(self.create_text(cx, y0 + 30, text="YOUR WEEK", font=mono_font(12, "bold")), YELLOW, 0)
        fade_item(self.create_text(cx, y0 + 68, text=span, font=display_font(24, "bold")), INK, 120)

        focus = data["focus_seconds"]
        big = self.create_text(cx, y0 + 140, text="0m", font=display_font(40, "bold"), fill=PINK)
        anim.animate(self, 1300, lambda t: self.itemconfigure(big, text=format_span(focus * t, False)),
                     delay_ms=300)
        fade_item(self.create_text(cx, y0 + 182, text="FOCUSED", font=mono_font(10)), INK_FAINT, 300)
        prev = data["prev_focus_seconds"]
        if prev and focus:
            change = round((focus - prev) / prev * 100)
            cmp_text, cmp_color = (f"+{change}% vs the week before", CYAN) if change >= 0 else \
                (f"{change}% vs the week before", PINK)
        elif focus:
            cmp_text, cmp_color = "Nothing timed the week before \u2014 this is your baseline", INK_DIM
        elif data["sessions"]:
            cmp_text, cmp_color = "Only older, untimed locks this week", INK_DIM
        else:
            cmp_text, cmp_color = (f"No locks this week \u2014 but {format_span(data['pomo_seconds'], False)} "
                                   "of Pomodoro", CYAN)
        fade_item(self.create_text(cx, y0 + 210, text=cmp_text, font=body_font(11)), cmp_color, 900)

        # day bars
        values = data["per_day"] if focus else data["sessions_per_day"]
        peak = max(values) or 1
        bar_w, gap = 44, 22
        left = cx - (7 * bar_w + 6 * gap) / 2
        base_y, max_h = y0 + 395, 122  # leaves room for the BEST DAY label under the comparison line
        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        for i in range(7):
            x1 = left + i * (bar_w + gap)
            best = i == data["best_day"]
            color = YELLOW if best else anim.blend(BORDER, PINK, 0.75)
            fade_item(self.create_text(x1 + bar_w / 2, base_y + 16, text=days[i], font=mono_font(9)),
                      INK if best else INK_FAINT, 500 + 60 * i)
            track = self.create_polygon(rounded_rect_points(x1, base_y - max_h, x1 + bar_w, base_y, 8),
                                        smooth=True, fill=BG, outline="")
            fade_item(track, SURFACE_2, 450 + 60 * i)
            bar = self.create_polygon(0, 0, 0, 0, fill=color, outline="", smooth=True)
            target = max_h * values[i] / peak

            def grow(t, bar=bar, x1=x1, target=target):
                hgt = target * t
                if hgt < 2:
                    self.coords(bar, 0, 0, 0, 0)
                else:
                    self.coords(bar, *rounded_rect_points(x1, base_y - hgt, x1 + bar_w, base_y, 8))
            anim.animate(self, 750, grow, easing=anim.ease_out_back, delay_ms=650 + 90 * i)
            if values[i]:
                label = format_span(values[i], False) if focus else f"{values[i]}x"
                fade_item(self.create_text(x1 + bar_w / 2, base_y - target - 12, text=label,
                                           font=mono_font(8, "bold")), INK if best else INK_DIM, 1300 + 90 * i)
            if best:
                fade_item(self.create_text(x1 + bar_w / 2, base_y - target - 28, text="BEST DAY",
                                           font=mono_font(8, "bold")), YELLOW, 1900)

        # stat tiles
        tiles = [("SESSIONS", data["sessions"], CYAN), ("POMODORO ROUNDS", data["pomo_rounds"], YELLOW),
                 ("DAY STREAK", stats.get("streak", 0), PINK), ("NEW BADGES", len(data["badges"]), CYAN)]
        tile_w = 130
        for i, (caption, value, color) in enumerate(tiles):
            tx = cx + (i - 1.5) * tile_w
            num = self.create_text(tx, y0 + 470, text="0", font=display_font(22, "bold"), fill=BG)
            fade_item(num, color, 1500 + 100 * i)
            anim.animate(self, 800, lambda t, n=num, v=value: self.itemconfigure(n, text=str(round(v * t))),
                         delay_ms=1500 + 100 * i)
            fade_item(self.create_text(tx, y0 + 500, text=caption, font=mono_font(8)), INK_FAINT, 1500 + 100 * i)

        y = y0 + 545
        if data["badges"]:
            fade_item(self.create_text(cx, y, text="Earned: " + ", ".join(data["badges"]), font=body_font(11),
                                       width=560, justify="center"), INK, 2000)
            y += 34
        if data["notes"]:
            fade_item(self.create_text(cx, y, text="YOU WORKED ON", font=mono_font(9, "bold")), CYAN, 2200)
            for j, note in enumerate(data["notes"]):
                fade_item(self.create_text(cx, y + 24 + j * 22, text=note, font=body_font(11, "italic"),
                                           width=560, justify="center"), INK_DIM, 2300 + 120 * j)
        fade_item(self.create_text(cx, h - 28, text="click anywhere to close", font=mono_font(9)), INK_FAINT, 2600)

        snd.play("chime")
        if focus or data["sessions"]:
            self._root().after(1600, lambda: anim._alive(self) and anim.confetti(
                self, cx, base_y - max_h, [PINK, CYAN, YELLOW], fade_to=BG, count=60))
        self.bind("<Button-1>", lambda e: self.leave(on_done))

    def level_up(self, level, title, rewards, on_done):
        """LEVEL UP: the new level number bounces in on turning rays, then
        the title and anything it unlocked."""
        if self._spin:
            self._spin.cancel()
        self.delete("all")
        cx, cy = self._center()
        cy -= 10
        ray = anim.blend(YELLOW, BG, 0.82)
        g = {"s": 0.0}

        def draw(phase):
            self.delete("medal")
            for i in range(14):
                a = math.radians(phase * 360 + i * (360 / 14))
                da = math.radians(5)
                self.create_polygon(cx, cy, cx + 240 * math.cos(a - da), cy + 240 * math.sin(a - da),
                                    cx + 240 * math.cos(a + da), cy + 240 * math.sin(a + da),
                                    fill=ray, outline="", tags="medal")
            s = g["s"]
            if s > 0.02:
                r = 74 * s
                self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=SURFACE, outline=YELLOW, width=5, tags="medal")
                self.create_text(cx, cy - 4 * s, text=str(level), fill=YELLOW,
                                 font=display_font(max(1, int(44 * s)), "bold"), tags="medal")
                self.create_text(cx, cy + 40 * s, text="LEVEL", fill=INK_DIM,
                                 font=mono_font(max(1, int(9 * s)), "bold"), tags="medal")
            self.tag_lower("medal")
        loop = anim.loop(self, 14000, draw)
        anim.animate(self, 750, lambda t: g.__setitem__("s", t), easing=anim.ease_out_back, delay_ms=120)
        snd.play("badge")
        self._root().after(350, lambda: anim._alive(self) and anim.confetti(
            self, cx, cy - 20, [YELLOW, PINK, CYAN], fade_to=BG, count=90))
        self.create_text(cx, cy - 135, text="LEVEL UP", fill=YELLOW, font=mono_font(13, "bold"))
        self.create_text(cx, cy + 118, text=title, fill=INK, font=display_font(24, "bold"))
        y = cy + 156
        for line in rewards:
            self.create_text(cx, y, text=line, fill=CYAN, font=body_font(11, "bold"))
            y += 24
        self.create_text(cx, y + 14, text="click to continue", fill=INK_FAINT, font=mono_font(9))

        def done():
            loop.cancel()
            self.leave(on_done)
        self.bind("<Button-1>", lambda e: done())
        self._root().after(5500, lambda: anim._alive(self) and not self._leaving and done())

    def rewards(self, items, hours, on_done):
        """REWARD(S) UNLOCKED: what focus hours just earned, on turning rays."""
        if self._spin:
            self._spin.cancel()
        self.delete("all")
        cx, cy = self._center()
        cy -= 40
        ray = anim.blend(CYAN, BG, 0.84)
        kinds = {"sound": ("FOCUS SOUND", CYAN), "font": ("FONT", YELLOW), "theme": ("THEME", PINK),
                 "celebration": ("CELEBRATION", YELLOW)}

        def draw(phase):
            self.delete("rays")
            for i in range(16):
                a = math.radians(phase * 360 + i * 22.5)
                da = math.radians(4)
                self.create_polygon(cx, cy, cx + 260 * math.cos(a - da), cy + 260 * math.sin(a - da),
                                    cx + 260 * math.cos(a + da), cy + 260 * math.sin(a + da),
                                    fill=ray, outline="", tags="rays")
            self.tag_lower("rays")
        loop = anim.loop(self, 16000, draw)
        snd.play("badge")
        self._root().after(300, lambda: anim._alive(self) and anim.confetti(
            self, cx, cy - 60, [CYAN, PINK, YELLOW], fade_to=BG, count=70))
        title = "REWARD UNLOCKED" if len(items) == 1 else f"{len(items)} REWARDS UNLOCKED"
        # a solid panel behind the text, so the turning rays don't run through it
        shown = min(len(items), 6)
        self.create_polygon(rounded_rect_points(cx - 300, cy - 150, cx + 300, cy - 40 + shown * 80 + 30, 16),
                            smooth=True, fill=BG, outline=BORDER, width=1)
        self.create_text(cx, cy - 120, text=title, fill=YELLOW, font=display_font(20, "bold"))
        self.create_text(cx, cy - 88, text=f"{hours:.1f} focus hours", fill=INK_DIM, font=mono_font(10))
        y = cy - 40
        for hrs, kind, _key, name, desc in items[:6]:
            tag, color = kinds[kind]
            self.create_text(cx, y, text=tag, fill=color, font=mono_font(9, "bold"))
            self.create_text(cx, y + 22, text=name, fill=INK, font=display_font(16, "bold"))
            self.create_text(cx, y + 46, text=desc, fill=INK_DIM, font=body_font(10), width=520, justify="center")
            y += 80
        self.create_text(cx, y + 6, text="Find them in Settings and Focus sounds  \u00b7  click to continue",
                         fill=INK_FAINT, font=mono_font(9))

        def done():
            loop.cancel()
            self.leave(on_done)
        self.bind("<Button-1>", lambda e: done())
        self._root().after(4500 + 1200 * len(items), lambda: anim._alive(self) and not self._leaving and done())

    def shortcuts(self, sections, on_done):
        """Every keyboard shortcut, grouped, with keys drawn as keycaps."""
        if self._spin:
            self._spin.cancel()
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        rows = sum(len(items) + 1 for _, items in sections)
        row_h = 34
        y = max(24, (h - (rows * row_h + 110)) / 2)
        cx = w / 2
        keys_right = cx - 20     # keycaps end here; descriptions start at cx + 4
        delay = 0

        def fade_item(item, color, delay):
            self.itemconfigure(item, fill=BG)
            anim.animate(self, 320, lambda t: anim._alive(self) and self.itemconfigure(
                item, fill=anim.blend(BG, color, t)), delay_ms=delay)

        fade_item(self.create_text(cx, y + 10, text="KEYBOARD SHORTCUTS", font=display_font(18, "bold")),
                  YELLOW, 0)
        y += 56
        for title, items in sections:
            fade_item(self.create_text(keys_right, y, text=title, anchor="e", font=mono_font(9, "bold")), CYAN, delay)
            y += row_h
            for keys, desc in items:
                x = keys_right
                for i, key in enumerate(reversed(keys)):
                    if i:
                        x -= text_width(key_sep(keys, len(keys) - i), mono_font(9)) + 12
                        fade_item(self.create_text(x + 6, y, text=key_sep(keys, len(keys) - i), anchor="w",
                                                   font=mono_font(9)), INK_FAINT, delay)
                    x = draw_keycap(self, x, y, key, delay)
                fade_item(self.create_text(cx + 4, y, text=desc, anchor="w", font=body_font(11)), INK, delay)
                y += row_h
                delay += 35
        fade_item(self.create_text(cx, h - 28, text="click anywhere, or press Esc, to close", font=mono_font(9)),
                  INK_FAINT, delay + 100)
        self.bind("<Button-1>", lambda e: self.leave(on_done))

    def leave(self, before=None):
        """Run before() (usually: rebuild the view underneath), then slide away."""
        if self._leaving or not anim._alive(self):
            return
        self._leaving = True
        if self._spin:
            self._spin.cancel()
        if before:
            before()
        raise_window(self)
        h = self.winfo_height()

        def frame(t):
            self.place_configure(y=-h * t)
        anim.animate(self, 520, frame, easing=anim.ease_in_out_cubic, on_done=self.destroy)


class TabBar(tk.Canvas):
    """Text tabs with an accent underline that slides to the selected tab.
    The leading edge moves first and the trailing edge catches up, so the
    underline stretches and snaps back as it travels."""

    H = 56

    def __init__(self, parent, tabs, current, on_select):
        super().__init__(parent, height=self.H, bg=BG, highlightthickness=0, bd=0)
        self.on_select = on_select
        self.current = current
        self.tabs = tabs
        self.spans = {}
        self.labels = dict(tabs)
        self._anim = None
        self._fit_width = None
        for key, label in tabs:
            tag = f"tab-{key}"
            # A background-coloured hit box, so the whole tab is clickable,
            # not just the glyph pixels.
            self.create_rectangle(0, 6, 0, self.H - 8, fill=BG, outline="", tags=(tag, f"{tag}-box"))
            self.create_text(0, self.H / 2 - 3, text=label, anchor="w",
                             fill=INK if key == current else INK_FAINT, tags=(tag, f"{tag}-text"))
            self.tag_bind(tag, "<ButtonRelease-1>", lambda e, k=key: self.on_select(k))
            self.tag_bind(tag, "<Enter>", lambda e, k=key: self._hover(k, True))
            self.tag_bind(tag, "<Leave>", lambda e, k=key: self._hover(k, False))
        self.status = self.create_text(0, self.H / 2 - 3, text="", anchor="w", font=mono_font(10, "bold"),
                                       fill=PINK)
        self._layout(11, 36)
        self.edges = list(self.spans[current])
        self.indicator = self.create_polygon(self._indicator_points(), smooth=True, fill=PINK, outline="")
        self.baseline = self.create_line(0, self.H - 1, 0, self.H - 1, fill=BORDER)
        self.bind("<Configure>", self._on_configure)

    def _layout(self, size, gap):
        """Place the tabs with this font size and gap; returns the x where they end."""
        self.font = mono_font(size, "bold")
        x = 32
        for key, label in self.tabs:
            w = text_width(label, self.font)
            self.coords(f"tab-{key}-box", x - gap / 3.6, 6, x + w + gap / 3.6, self.H - 8)
            self.coords(f"tab-{key}-text", x, self.H / 2 - 3)
            self.itemconfigure(f"tab-{key}-text", font=self.font)
            self.spans[key] = (x, x + w)
            x += w + gap
        self.status_x = x
        self.coords(self.status, x, self.H / 2 - 3)
        return x - gap

    def _on_configure(self, event):
        self.coords(self.baseline, 0, self.H - 1, event.width, self.H - 1)
        if event.width != self._fit_width:
            self.fit(event.width)

    def fit(self, width=None):
        """Wide fonts or a narrow window: tighten the gaps, then shrink the
        text, until the tabs clear the SOUND button on the right."""
        width = width or self.winfo_width()
        if width <= 1:
            return
        self._fit_width = width
        btn = getattr(self.winfo_toplevel(), "sound_btn", None)
        reserve = (int(btn["width"]) if btn is not None and anim._alive(btn) else 110) + 22 + 24
        room = width - reserve
        for size, gap in ((11, 36), (11, 28), (11, 22), (10, 20), (10, 16), (9, 14), (8, 12)):
            if self._layout(size, gap) <= room:
                break
        if self._anim:
            self._anim.cancel()
        self.edges = list(self.spans[self.current])
        self.coords(self.indicator, *self._indicator_points())

    def set_status(self, text, color=None):
        """Small live text after the last tab, e.g. a running timer."""
        self.itemconfigure(self.status, text=text, fill=color or PINK)

    def set_tab_text(self, key, text=None, color=None):
        """Temporarily show text (e.g. a countdown) in place of a tab's
        label; text=None restores the label. Takes no extra room, so it can
        never run under the buttons on the right in a narrow window."""
        item = f"tab-{key}-text"
        label = self.labels[key]
        if text is None:
            self.itemconfigure(item, text=label, fill=INK if key == self.current else INK_FAINT)
        else:
            self.itemconfigure(item, text=text, fill=color or PINK)

    def _indicator_points(self):
        x1, x2 = self.edges
        return rounded_rect_points(x1, self.H - 15, x2, self.H - 11, 2)

    def _hover(self, key, inside):
        self.configure(cursor="hand2" if inside else "")
        if key != self.current and self.itemcget(f"tab-{key}-text", "text") == self.labels[key]:
            self.itemconfigure(f"tab-{key}-text", fill=INK_DIM if inside else INK_FAINT)

    def select(self, key):
        if key == self.current:
            return
        old = self.current
        self.current = key
        self.itemconfigure(f"tab-{old}-text", fill=INK_FAINT)
        self.itemconfigure(f"tab-{key}-text", fill=INK)
        if self._anim:
            self._anim.cancel()
        (s1, s2), (e1, e2) = list(self.edges), self.spans[key]
        moving_right = e1 > s1

        def frame(t):
            fast = anim.ease_out_cubic(min(1.0, t * 1.6))
            slow = anim.ease_in_out_cubic(t)
            t1, t2 = (slow, fast) if moving_right else (fast, slow)
            self.edges = [s1 + (e1 - s1) * t1, s2 + (e2 - s2) * t2]
            self.coords(self.indicator, *self._indicator_points())
        self._anim = anim.animate(self, 420, frame, easing=anim.linear)


class TaskCheck(tk.Canvas):
    """An animated checkbox: the box fills and the tick draws itself in."""

    S = 24

    def __init__(self, parent, done, on_click):
        super().__init__(parent, width=self.S, height=self.S, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.done = done
        self.t = 1.0 if done else 0.0
        self.hover = 0.0
        self._fade = 1.0
        self._anim = None
        self.bind("<ButtonRelease-1>", lambda e: on_click())
        self.bind("<Enter>", lambda e: self._set_hover(1.0))
        self.bind("<Leave>", lambda e: self._set_hover(0.0))
        self._draw()

    def _set_hover(self, v):
        self.hover = v
        self._draw()

    def set_done(self, done):
        self.done = done
        if self._anim:
            self._anim.cancel()
        start, end = self.t, (1.0 if done else 0.0)

        def frame(t):
            self.t = start + (end - start) * t
            self._draw()
        self._anim = anim.animate(self, 320 if done else 180, frame, easing=anim.ease_out_back if done else anim.ease_out_cubic)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        f = lambda c: anim.blend(self["bg"], c, self._fade)
        s, t = self.S, max(0.0, min(1.0, self.t))
        self.delete("all")
        ring = anim.blend(BORDER_STRONG, INK_DIM, self.hover) if t < 0.5 else PINK
        self.create_polygon(rounded_rect_points(2, 2, s - 2, s - 2, 6), smooth=True,
                            fill=f(anim.blend(SURFACE_2, PINK, t)), outline=f(ring), width=1.5)
        if t > 0.05:
            # the tick: two strokes drawn in order, as far as t has got
            pts = [(6.5, 12.5), (10.5, 16.5), (17.5, 7.5)]
            seg1 = min(1.0, t * 2)
            seg2 = max(0.0, t * 2 - 1)
            (x0, y0), (x1, y1), (x2, y2) = pts
            line = [x0, y0, x0 + (x1 - x0) * seg1, y0 + (y1 - y0) * seg1]
            if seg2 > 0:
                line += [x1 + (x2 - x1) * seg2, y1 + (y2 - y1) * seg2]
            self.create_line(*line, fill=f(ON_PINK), width=2.6, capstyle="round", joinstyle="round")


class TaskRow(tk.Frame):
    """One task: checkbox, text (struck through when done) and a remove ×
    that shows on hover."""

    def __init__(self, parent, task, on_toggle, on_remove):
        super().__init__(parent, bg=parent["bg"])
        self.task = task
        self.check = TaskCheck(self, task.get("done", False), on_toggle)
        self.check.pack(side="left", padx=(0, 10), pady=4)
        self.label = tk.Label(self, text=task["text"], bg=parent["bg"], anchor="w", justify="left",
                              wraplength=520, cursor="hand2")
        self.label.pack(side="left", fill="x", expand=True)
        self.label.bind("<ButtonRelease-1>", lambda e: on_toggle())
        self.remove = tk.Label(self, text="\u00d7", font=body_font(13), bg=parent["bg"], fg=parent["bg"],
                               cursor="hand2")
        self.remove.pack(side="right", padx=(8, 2))
        self.remove.bind("<ButtonRelease-1>", lambda e: on_remove())
        self.remove.bind("<Enter>", lambda e: self.remove.config(fg=PINK))
        self.remove.bind("<Leave>", lambda e: self.remove.config(fg=INK_FAINT))
        for w in (self, self.label, self.check):
            w.bind("<Enter>", lambda e: self._hover(True), add="+")
            w.bind("<Leave>", lambda e: self._hover(False), add="+")
        self._style()

    def _hover(self, inside):
        if not anim._alive(self.remove):
            return
        inside = inside or is_inside(self, *self.winfo_pointerxy())
        self.remove.config(fg=INK_FAINT if inside else self["bg"])

    def _style(self):
        done = self.task.get("done", False)
        font = body_font(11)
        self.label.config(font=(font[0], font[1], "overstrike") if done else font, fg=INK_FAINT if done else INK)

    def set_done(self, done):
        self.task["done"] = done
        self.check.set_done(done)
        self._style()


class MonthCalendar(tk.Canvas):
    """A month as a Monday-first grid. Each day is shaded by how long you
    focused; a yellow dot marks a met daily goal. Click a day to pick it."""

    HEAD = 26

    def __init__(self, parent, month, focus_by, goal_days, selected, on_pick, intro=True):
        first = month.replace(day=1)
        days_in_month = ((first + timedelta(days=32)).replace(day=1) - first).days
        self.ROWS = math.ceil((first.weekday() + days_in_month) / 7)   # 4-6, as the month needs
        super().__init__(parent, height=self.HEAD + self.ROWS * 46, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.month, self.focus_by, self.goal_days = month, focus_by, goal_days
        self.selected, self.on_pick = selected, on_pick
        self.hover = None
        self.grow = 0.0 if intro else 1.0
        self._fade = 1.0
        self.start = first - timedelta(days=first.weekday())
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<ButtonRelease-1>", self._on_click)
        if intro:
            anim.animate(self, 600, self._set_grow, easing=anim.ease_out_cubic, delay_ms=250)

    def _set_grow(self, t):
        self.grow = t
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _cell(self, x, y):
        w = self.winfo_width()
        if w <= 1 or y < self.HEAD:
            return None
        col, row = int(x // (w / 7)), int((y - self.HEAD) // 46)
        if 0 <= col < 7 and 0 <= row < self.ROWS:
            return self.start + timedelta(days=row * 7 + col)
        return None

    def _on_motion(self, event):
        self._set_hover(self._cell(event.x, event.y))

    def _set_hover(self, day):
        if day != self.hover:
            self.hover = day
            self._draw()

    def _on_click(self, event):
        day = self._cell(event.x, event.y)
        if day is not None and day.month == self.month.month and day <= date.today():
            self.selected = day
            self._draw()
            self.on_pick(day)

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        f = lambda c: anim.blend(self["bg"], c, self._fade)
        self.delete("all")
        cw = w / 7
        for i, name in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")):
            self.create_text(cw * (i + 0.5), 10, text=name, fill=f(INK_FAINT), font=mono_font(8))
        peak = max([v for d, v in self.focus_by.items() if d.month == self.month.month] + [3600])
        today = date.today()
        for k in range(self.ROWS * 7):
            day = self.start + timedelta(days=k)
            if day.month != self.month.month:
                continue
            col, row = k % 7, k // 7
            x0, y0 = col * cw + 3, self.HEAD + row * 46 + 3
            x1, y1 = x0 + cw - 6, y0 + 40
            secs = self.focus_by.get(day, 0)
            level = min(1.0, secs / peak) * self.grow
            fill = anim.blend(SURFACE_2, PINK, 0.15 + 0.85 * level) if secs > 0 else SURFACE_2
            outline = ""
            if day == self.selected:
                outline = YELLOW
            elif day == self.hover and day <= today:
                outline = INK_DIM
            elif day == today:
                outline = CYAN
            self.create_polygon(rounded_rect_points(x0, y0, x1, y1, 6), smooth=True, fill=f(fill),
                                outline=f(outline) if outline else "", width=2)
            future = day > today
            self.create_text(x0 + 7, y0 + 11, text=str(day.day), anchor="w", font=mono_font(9, "bold"),
                             fill=f(INK_FAINT if future else (ON_PINK if level > 0.6 else INK)))
            if secs >= 60:
                self.create_text(x1 - 6, y1 - 9, text=format_minutes(secs // 60), anchor="e", font=mono_font(7),
                                 fill=f(ON_PINK if level > 0.6 else INK_DIM))
            if day.isoformat() in self.goal_days:
                self.create_oval(x1 - 12, y0 + 6, x1 - 5, y0 + 13, fill=f(YELLOW), outline="")


class HourChart(tk.Canvas):
    """24 little bars, one per hour of the day; the busiest hour highlighted."""

    def __init__(self, parent, per_hour, intro=True):
        super().__init__(parent, height=96, bg=parent["bg"], highlightthickness=0, bd=0)
        self.per_hour = per_hour
        self.grow = 0.0 if intro else 1.0
        self._fade = 1.0
        self.bind("<Configure>", lambda e: self._draw())
        if intro:
            anim.animate(self, 700, self._set_grow, easing=anim.ease_out_cubic, delay_ms=300)

    def _set_grow(self, t):
        self.grow = t
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        f = lambda c: anim.blend(self["bg"], c, self._fade)
        self.delete("all")
        peak = max(self.per_hour) or 1
        top_hour = self.per_hour.index(max(self.per_hour)) if max(self.per_hour) else None
        slot = w / 24
        bw = max(3, slot * 0.6)
        base, top = 70, 6
        for hour, n in enumerate(self.per_hour):
            cx = slot * (hour + 0.5)
            h = (base - top) * n / peak * self.grow
            color = YELLOW if hour == top_hour else anim.blend(BORDER, PINK, 0.7)
            self.create_rectangle(cx - bw / 2, top, cx + bw / 2, base, fill=f(SURFACE_2), outline="")
            if h >= 1:
                self.create_rectangle(cx - bw / 2, base - h, cx + bw / 2, base, fill=f(color), outline="")
            if hour % 6 == 0:
                self.create_text(cx, base + 14, text=hour_label(hour), fill=f(INK_FAINT), font=mono_font(8))


def hour_label(hour):
    return {0: "12am", 12: "12pm"}.get(hour, f"{hour % 12}{'am' if hour < 12 else 'pm'}")


class GoalRing(tk.Canvas):
    """Today's progress toward the daily goal: a ring that fills clockwise
    (easing to each new value) with the percentage inside. Turns yellow with
    a check mark once the goal is met."""

    SIZE = 108

    def __init__(self, parent, fraction, intro=True):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, bg=parent["bg"], highlightthickness=0, bd=0)
        self.target = max(0.0, fraction)
        self.shown = 0.0 if intro else self.target
        self._fade = 1.0
        self._anim = None
        if intro:
            self._tween(900, delay_ms=350)
        self._draw()

    def set_fraction(self, fraction):
        fraction = max(0.0, fraction)
        if abs(fraction - self.target) < 1e-4:
            return
        self.target = fraction
        self._tween(600)

    def _tween(self, ms, delay_ms=0):
        if self._anim:
            self._anim.cancel()
        start = self.shown

        def frame(t):
            self.shown = start + (self.target - start) * t
            self._draw()
        self._anim = anim.animate(self, ms, frame, easing=anim.ease_out_cubic, delay_ms=delay_ms)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        f = lambda c: anim.blend(self["bg"], c, self._fade)
        size, pad, width = self.SIZE, 10, 9
        done = self.shown >= 1.0
        color = YELLOW if done else PINK
        self.delete("ring")
        self.create_oval(pad, pad, size - pad, size - pad, outline=f(SURFACE_2), width=width, tags="ring")
        extent = 359.9 * min(1.0, self.shown)
        if extent > 0.5:
            self.create_arc(pad, pad, size - pad, size - pad, start=90, extent=-extent, style="arc",
                            outline=f(color), width=width, tags="ring")
        text = "\u2713" if done else f"{int(min(0.999, self.shown) * 100)}%"
        self.create_text(size / 2, size / 2, text=text, fill=f(INK if not done else YELLOW),
                         font=display_font(20 if done else 15, "bold"), tags="ring")
        self.tag_lower("ring")   # keep confetti in front


class GoalHistory(tk.Canvas):
    """The last two weeks against the daily goal: one bar per day, a dashed
    goal line, days that met it in yellow. Hover a bar for its total."""

    def __init__(self, parent, days, seconds, goal_seconds, met, on_hover=None, intro=True):
        super().__init__(parent, height=150, bg=parent["bg"], highlightthickness=0, bd=0)
        self.days, self.seconds, self.goal, self.met = days, seconds, goal_seconds, met
        self.on_hover = on_hover
        self.grow = 0.0 if intro else 1.0
        self.hover = None
        self._fade = 1.0
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        if intro:
            anim.animate(self, 800, self._set_grow, easing=anim.ease_out_cubic, delay_ms=350)

    def _set_grow(self, t):
        self.grow = t
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _geometry(self):
        w = self.winfo_width()
        n = len(self.days)
        slot = w / n
        return w, n, slot, min(26, slot * 0.62)

    def _on_motion(self, event):
        w, n, slot, _ = self._geometry()
        if w > 1:
            self._set_hover(max(0, min(n - 1, int(event.x // slot))))

    def _set_hover(self, i):
        if i == self.hover:
            return
        self.hover = i
        self._draw()
        if self.on_hover:
            if i is None:
                self.on_hover(None)
            else:
                day = self.days[i]
                state = "goal met" if day.isoformat() in self.met else "not met"
                self.on_hover(f"{fmt_date(day, '%a %-d %b')}  ·  {format_minutes(self.seconds[i] // 60)}  ·  {state}")

    def _draw(self):
        w, n, slot, bar_w = self._geometry()
        if w <= 1:
            return
        f = lambda c: anim.blend(self["bg"], c, self._fade)
        self.delete("all")
        top, base = 14, 120
        peak = max(max(self.seconds), self.goal * 1.15, 1)
        goal_y = base - (base - top) * self.goal / peak
        for i, day in enumerate(self.days):
            cx = slot * (i + 0.5)
            met = day.isoformat() in self.met
            color = YELLOW if met else anim.blend(BORDER, PINK, 0.7)
            if i == self.hover:
                color = anim.lighten(color, 0.25)
            self.create_polygon(rounded_rect_points(cx - bar_w / 2, top, cx + bar_w / 2, base, 6), smooth=True,
                                fill=f(SURFACE_2), outline="")
            h = (base - top) * min(1.0, self.seconds[i] / peak) * self.grow
            if h > 3:
                self.create_polygon(rounded_rect_points(cx - bar_w / 2, base - h, cx + bar_w / 2, base, 6),
                                    smooth=True, fill=f(color), outline="")
            today = i == n - 1
            self.create_text(cx, base + 16, text="TODAY" if today and slot > 40 else day.strftime("%a")[0],
                             fill=f(INK if today else INK_FAINT), font=mono_font(8, "bold" if today else "normal"))
        self.create_line(0, goal_y, w, goal_y, fill=f(CYAN), dash=(4, 4))
        label = self.create_text(4, goal_y, text=" GOAL ", anchor="w", fill=f(CYAN), font=mono_font(7, "bold"))
        x1, y1, x2, y2 = self.bbox(label)
        self.tag_lower(self.create_rectangle(x1, y1, x2, y2, fill=f(self["bg"]), outline=""), label)


class BarChart(tk.Canvas):
    """Vertical bars that grow in one after another. Values sit above the
    bars; the highlighted bar (e.g. this week) is drawn in full colour."""

    def __init__(self, parent, labels, values, color, highlight=None, height=170, intro=True):
        super().__init__(parent, height=height, bg=parent["bg"], highlightthickness=0, bd=0)
        self.labels, self.values = labels, values
        self.color = color
        self.highlight = highlight
        self.grow = [0.0 if intro else 1.0] * len(values)
        self.hover = None
        self._fade = 1.0
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        if intro:
            for i in range(len(values)):
                anim.animate(self, 650, lambda t, i=i: self._set_grow(i, t),
                             easing=anim.ease_out_back, delay_ms=350 + i * 70)

    def _set_grow(self, i, t):
        self.grow[i] = t
        self._draw()

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self._draw()

    def _on_motion(self, event):
        w = self.winfo_width()
        n = len(self.values)
        i = int(event.x / (w / n)) if w > 1 and n else None
        self._set_hover(i if i is not None and 0 <= i < n else None)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        w, h = self.winfo_width(), int(self["height"])
        n = len(self.values)
        if w <= 1 or not n:
            return
        fade = lambda c: anim.blend(BG, c, self._fade)
        self.delete("all")
        top, bottom = 22, 26
        plot_h = h - top - bottom
        base_y = h - bottom
        peak = max(self.values) or 1
        slot = w / n
        bar_w = min(44, slot * 0.58)
        self.create_line(0, base_y, w, base_y, fill=fade(BORDER))
        for i, (label, value) in enumerate(zip(self.labels, self.values)):
            cx = slot * (i + 0.5)
            g = self.grow[i]
            bh = plot_h * value / peak * g
            color = self.color if i == self.highlight else anim.blend(BORDER, self.color, 0.6)
            if i == self.hover:
                color = anim.lighten(color, 0.2)
            if value and bh > 1:
                self.create_polygon(rounded_rect_points(cx - bar_w / 2, base_y - bh, cx + bar_w / 2, base_y, 5),
                                    smooth=True, fill=fade(color), outline="")
            if g > 0.85:
                ink = INK if i in (self.hover, self.highlight) else INK_DIM
                self.create_text(cx, base_y - bh - 10, text=str(value), font=mono_font(9, "bold"), fill=fade(ink))
            self.create_text(cx, base_y + 13, text=label, font=mono_font(9),
                             fill=fade(INK if i == self.highlight else INK_FAINT))


class HBarList(tk.Canvas):
    """Ranked rows: label, a bar proportional to the value, the value."""

    ROW_H = 32

    def __init__(self, parent, rows, intro=True):
        super().__init__(parent, height=max(1, len(rows)) * self.ROW_H, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.rows = rows  # [(label, value, color)]
        self.grow = [0.0 if intro else 1.0] * len(rows)
        self._fade = 1.0
        self.label_w = max([text_width(r[0], body_font(10)) for r in rows] + [80]) + 18
        self.bind("<Configure>", lambda e: self._draw())
        if intro:
            for i in range(len(rows)):
                anim.animate(self, 700, lambda t, i=i: self._set_grow(i, t),
                             easing=anim.ease_out_cubic, delay_ms=400 + i * 90)

    def _set_grow(self, i, t):
        self.grow[i] = t
        self._draw()

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        fade = lambda c: anim.blend(BG, c, self._fade)
        self.delete("all")
        peak = max([r[1] for r in self.rows] + [1])
        # room for the widest value (it grows with the Text size setting)
        value_w = max(text_width(str(round(v)), mono_font(10, "bold")) for _, v, _ in self.rows) + 14 if self.rows else 44
        x0, x_end = self.label_w, w - max(44, value_w)
        for i, (label, value, color) in enumerate(self.rows):
            cy = i * self.ROW_H + self.ROW_H / 2
            self.create_text(0, cy, text=label, anchor="w", font=body_font(10), fill=fade(INK))
            self.create_polygon(rounded_rect_points(x0, cy - 5, x_end, cy + 5, 5), smooth=True,
                                fill=fade(SURFACE_2), outline="")
            bar_end = x0 + (x_end - x0) * value / peak * self.grow[i]
            if bar_end - x0 > 10:
                self.create_polygon(rounded_rect_points(x0, cy - 5, bar_end, cy + 5, 5), smooth=True,
                                    fill=fade(color), outline="")
            self.create_text(w, cy, text=str(round(value * self.grow[i])), anchor="e",
                             font=mono_font(10, "bold"), fill=fade(INK_DIM))


def count_up(label, value, fmt=str, duration=900, delay=0):
    """Animate a label's number from 0 to value, rendered through fmt."""
    if not value:
        label.config(text=fmt(value))
        return
    label.config(text=fmt(0))
    anim.animate(label, duration, lambda t: label.config(text=fmt(value * t)), delay_ms=delay)


# ---------- badges ----------

def accent_colors(name):
    """(fill, ink-on-fill) for a badge accent name."""
    return {"pink": (PINK, ON_PINK), "cyan": (CYAN, ON_CYAN), "yellow": (YELLOW, ON_YELLOW)}[name]


def draw_icon(cv, kind, x, y, k, color, bg, tag=None):
    """A small vector icon of half-size k centred on (x, y)."""
    def pts(seq):
        return [v for px, py in seq for v in (x + px * k, y + py * k)]
    w = max(1.5, k / 5)
    if kind == "lock":
        draw_padlock(cv, x, y, scale=k / 44, body=color, shackle=color, hole=bg, tag=tag)
    elif kind == "clock":
        cv.create_oval(x - k, y - k, x + k, y + k, outline=color, width=w, tags=tag)
        cv.create_line(x, y, x, y - 0.6 * k, fill=color, width=w, capstyle="round", tags=tag)
        cv.create_line(x, y, x + 0.45 * k, y + 0.1 * k, fill=color, width=w, capstyle="round", tags=tag)
    elif kind == "flame":
        cv.create_polygon(pts([(0, -1), (0.5, -0.2), (0.62, 0.4), (0.3, 0.9), (0, 1), (-0.3, 0.9),
                               (-0.62, 0.4), (-0.45, -0.1), (-0.2, 0.15)]),
                          smooth=True, fill=color, outline="", tags=tag)
    elif kind == "star":
        star = []
        for i in range(10):
            r = 1.0 if i % 2 == 0 else 0.45
            a = -math.pi / 2 + i * math.pi / 5
            star.append((r * math.cos(a), r * math.sin(a)))
        cv.create_polygon(pts(star), fill=color, outline="", tags=tag)
    elif kind == "sun":
        cv.create_oval(x - 0.45 * k, y - 0.45 * k, x + 0.45 * k, y + 0.45 * k, fill=color, outline="", tags=tag)
        for i in range(8):
            a = i * math.pi / 4
            cv.create_line(x + 0.68 * k * math.cos(a), y + 0.68 * k * math.sin(a),
                           x + k * math.cos(a), y + k * math.sin(a),
                           fill=color, width=w, capstyle="round", tags=tag)
    elif kind == "moon":
        cv.create_oval(x - 0.85 * k, y - 0.85 * k, x + 0.85 * k, y + 0.85 * k, fill=color, outline="", tags=tag)
        cv.create_oval(x - 0.35 * k, y - 1.1 * k, x + 1.05 * k, y + 0.45 * k, fill=bg, outline="", tags=tag)
    elif kind == "note":
        cv.create_rectangle(x - 0.7 * k, y - k, x + 0.7 * k, y + k, outline=color, width=w, tags=tag)
        for dy in (-0.45, 0, 0.45):
            cv.create_line(x - 0.38 * k, y + dy * k, x + 0.38 * k, y + dy * k, fill=color, width=w, tags=tag)
    elif kind == "bolt":
        cv.create_polygon(pts([(0.2, -1), (-0.6, 0.15), (-0.05, 0.15), (-0.25, 1), (0.6, -0.2), (0.05, -0.2)]),
                          fill=color, outline="", tags=tag)
    elif kind == "tomato":
        cv.create_oval(x - 0.85 * k, y - 0.6 * k, x + 0.85 * k, y + k, fill=color, outline="", tags=tag)
        leaf = []
        for i in range(10):
            r = 0.55 if i % 2 == 0 else 0.2
            a = -math.pi / 2 + i * math.pi / 5
            leaf.append((r * math.cos(a), -0.55 + r * 0.6 * math.sin(a)))
        cv.create_polygon(pts(leaf), fill=bg, outline="", tags=tag)
        cv.create_line(x, y - 0.6 * k, x + 0.15 * k, y - k, fill=color, width=w, tags=tag)
    elif kind == "shield":
        cv.create_polygon(pts([(-0.8, -0.9), (0.8, -0.9), (0.8, 0.1), (0, 1), (-0.8, 0.1)]),
                          fill=color, outline="", tags=tag)


def draw_medal(cv, cx, cy, s, badge, fade=1.0, tag=None):
    """A ribboned medal of scale s whose disc is centred on (cx, cy).
    Earned badges are drawn in their accent colour; unearned ones in grey."""
    def f(c):
        return anim.blend(BG, c, fade) if fade < 1 else c
    if badge["earned"]:
        fill, ink = accent_colors(badge["accent"])
        rim = anim.lighten(fill, 0.3)
        tail_l, tail_r = anim.blend(fill, BG, 0.25), anim.blend(fill, "#000000", 0.3)
    else:
        fill, ink, rim = SURFACE_2, INK_FAINT, BORDER_STRONG
        tail_l = tail_r = BORDER
    left = [(-6, 14), (-22, 46), (-15, 42), (-9, 50), (6, 18)]
    for tail, color in ((left, tail_l), ([(-px, py) for px, py in left], tail_r)):
        cv.create_polygon([v for px, py in tail for v in (cx + px * s, cy + py * s)],
                          fill=f(color), outline="", tags=tag)
    r = 30 * s
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=f(rim), outline="", tags=tag)
    r2 = r - 4 * s
    cv.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill=f(fill), outline="", tags=tag)
    draw_icon(cv, badge["icon"], cx, cy - 7 * s, 8.5 * s, f(ink), f(fill), tag=tag)
    if s > 0.35:
        cv.create_text(cx, cy + 13 * s, text=badge["text"], fill=f(ink),
                       font=mono_font(max(6, int(8 * s)), "bold"), tags=tag)


class Medal(tk.Canvas):
    """A badge medal: pops in with a bounce, grows a little on hover, and
    earned medals catch an occasional sparkle."""

    def __init__(self, parent, badge, size=96, intro_delay=None):
        super().__init__(parent, width=size, height=size + 4, bg=parent["bg"], highlightthickness=0, bd=0)
        self.badge = badge
        self.size = size
        self.grow = 1.0 if intro_delay is None else 0.0
        self.hover = 0.0
        self.sparkle = None
        self._fade = 1.0
        self._hover_anim = None
        self.bind("<Enter>", lambda e: self._tween_hover(1.0))
        self.bind("<Leave>", lambda e: self._tween_hover(0.0))
        if intro_delay is not None:
            anim.animate(self, 650, self._set_grow, easing=anim.ease_out_back, delay_ms=intro_delay)
        if badge["earned"]:
            anim.loop(self, random.randint(3800, 5200), self._set_sparkle,
                      delay_ms=random.randint(800, 3000))
        self._draw()

    def _set_grow(self, t):
        self.grow = t
        self._draw()

    def _set_sparkle(self, phase):
        visible = phase < 0.22
        if visible or self.sparkle is not None:
            self.sparkle = phase if visible else None
            self._draw()

    def _tween_hover(self, target):
        if self._hover_anim:
            self._hover_anim.cancel()
        start = self.hover

        def frame(t):
            self.hover = start + (target - start) * t
            self._draw()
        self._hover_anim = anim.animate(self, 220, frame, easing=anim.ease_out_back)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size / 96 * self.grow * (1 + 0.1 * self.hover)
        if s <= 0.03:
            return
        cx, cy = self.size / 2, self.size * 0.4
        draw_medal(self, cx, cy, s, self.badge, fade=self._fade)
        if self.sparkle is not None:
            p = math.sin(math.pi * self.sparkle / 0.22)
            sx, sy, k = cx + 17 * s, cy - 17 * s, 7 * s * p
            self.create_polygon(sx, sy - k, sx + k * 0.25, sy - k * 0.25, sx + k, sy, sx + k * 0.25, sy + k * 0.25,
                                sx, sy + k, sx - k * 0.25, sy + k * 0.25, sx - k, sy, sx - k * 0.25, sy - k * 0.25,
                                fill="#ffffff", outline="")


class MiniBar(tk.Canvas):
    """A thin static progress bar that fills in once."""

    def __init__(self, parent, fraction, color, intro=True):
        super().__init__(parent, height=6, bg=parent["bg"], highlightthickness=0, bd=0)
        self.fraction = max(0.0, min(1.0, fraction))
        self.color = color
        self.grow = 0.0 if intro else 1.0
        self.bind("<Configure>", lambda e: self._draw())
        if intro:
            anim.animate(self, 800, self._set_grow, delay_ms=500)

    def _set_grow(self, t):
        self.grow = t
        self._draw()

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        self.delete("all")
        self.create_polygon(rounded_rect_points(0, 0, w, 6, 3), smooth=True, fill=SURFACE_2, outline="")
        fill_w = w * self.fraction * self.grow
        if fill_w > 6:
            self.create_polygon(rounded_rect_points(0, 0, fill_w, 6, 3), smooth=True, fill=self.color, outline="")


class Slider(tk.Canvas):
    """A horizontal 0..1 slider: click or drag; the knob eases to the spot."""

    def __init__(self, parent, value, on_change, width=180, accent=None):
        super().__init__(parent, width=width, height=26, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.value = max(0.0, min(1.0, value))
        self.shown = self.value
        self.on_change = on_change
        self.accent = accent or CYAN
        self._anim = None
        self._fade = 1.0
        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _on_pointer(self, event):
        w = int(self["width"])
        value = max(0.0, min(1.0, (event.x - 10) / (w - 20)))
        self.value = value
        self.on_change(value)
        if self._anim:
            self._anim.cancel()
        start = self.shown

        def frame(t):
            self.shown = start + (value - start) * t
            self._draw()
        self._anim = anim.animate(self, 120, frame)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        w = int(self["width"])
        f = lambda c: anim.blend(BG, c, self._fade)
        self.delete("all")
        x0, x1, cy = 10, w - 10, 13
        self.create_polygon(rounded_rect_points(x0, cy - 3, x1, cy + 3, 3), smooth=True, fill=f(SURFACE_2), outline="")
        kx = x0 + (x1 - x0) * self.shown
        if kx - x0 > 4:
            self.create_polygon(rounded_rect_points(x0, cy - 3, kx, cy + 3, 3), smooth=True, fill=f(self.accent),
                                outline="")
        self.create_oval(kx - 8, cy - 8, kx + 8, cy + 8, fill=f(INK), outline=f(self.accent), width=2)


class Equalizer(tk.Canvas):
    """Little bouncing bars that dance while a focus sound plays."""

    def __init__(self, parent, is_playing, color=None):
        super().__init__(parent, width=34, height=22, bg=parent["bg"], highlightthickness=0, bd=0)
        self.is_playing = is_playing
        self.color = color or PINK
        self.level = 0.0
        anim.loop(self, 1000, self._frame)

    def _frame(self, phase):
        target = 1.0 if self.is_playing() else 0.0
        self.level += (target - self.level) * 0.15
        self.delete("all")
        t = time.monotonic()
        for i in range(4):
            h = 3 + 16 * self.level * (0.5 + 0.5 * math.sin(t * (5.3 + i * 1.7) + i * 1.3)) ** 2
            x = 3 + i * 8
            self.create_rectangle(x, 21 - h, x + 5, 21, fill=anim.blend(BORDER, self.color, 0.3 + 0.7 * self.level),
                                  outline="")


class ThemeSwatch(tk.Canvas):
    """A tiny preview of a theme drawn in that theme's own colours."""

    def __init__(self, parent, key, label, selected, on_pick, locked_level=None, locked_text=None):
        super().__init__(parent, width=150, height=74, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.key, self.label, self.selected, self.on_pick = key, label, selected, on_pick
        self.locked_level = locked_level   # set while the theme is still a level-up reward
        self.locked_text = locked_text or (f"LV {locked_level}" if locked_level else None)
        self.hover = 0.0
        self._anim = None
        self._fade = 1.0
        self.bind("<ButtonRelease-1>", lambda e: self.on_pick(self.key, self))
        self.bind("<Enter>", lambda e: self._tween(1.0))
        self.bind("<Leave>", lambda e: self._tween(0.0))
        self._draw()

    def _tween(self, target):
        if self._anim:
            self._anim.cancel()
        start = self.hover

        def frame(t):
            self.hover = start + (target - start) * t
            self._draw()
        self._anim = anim.animate(self, 150, frame)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        th = _THEMES[self.key]
        dim = 0.32 if self.locked_text else 1.0
        f = lambda c: anim.blend(BG, c, self._fade * dim)
        self.delete("all")
        lift = 2 * self.hover
        ring = th["PINK"] if self.selected else anim.blend(BORDER, INK_DIM, self.hover)
        self.create_polygon(rounded_rect_points(2, 2 - lift, 148, 72 - lift, 10), smooth=True,
                            fill=f(th["BG"]), outline=f(ring), width=2 if self.selected else 1)
        self.create_polygon(rounded_rect_points(12, 12 - lift, 92, 44 - lift, 6), smooth=True,
                            fill=f(th["SURFACE"]), outline=f(th["BORDER"]))
        for i, accent in enumerate((th["PINK"], th["CYAN"], th["YELLOW"])):
            self.create_polygon(rounded_rect_points(20, 18 + i * 8 - lift, 20 + (58 - i * 14), 22 + i * 8 - lift, 2),
                                smooth=True, fill=f(accent), outline="")
        self.create_oval(104, 16 - lift, 124, 36 - lift, fill=f(th["PINK"]), outline="")
        self.create_text(12, 58 - lift, text=self.label + ("  \u2713" if self.selected else ""), anchor="w",
                         font=mono_font(9, "bold"), fill=f(th["INK"]))
        if self.locked_text:
            ink = anim.blend(BG, INK, self._fade)
            draw_padlock(self, 114, 26 - lift, scale=0.26, body=ink, shackle=ink, hole=anim.blend(BG, BG, 1))
            self.create_text(140, 58 - lift, text=self.locked_text, anchor="e",
                             font=mono_font(9, "bold"), fill=ink)


class FontPresetCard(tk.Canvas):
    """A font preset drawn in its own fonts: the name as a headline, then a
    mono and a body sample. Click to choose it."""

    def __init__(self, parent, key, selected, on_pick, locked_text=None):
        self.W, self.H = round(232 * TEXT_SCALE), round(96 * TEXT_SCALE)
        self.locked_text = locked_text
        super().__init__(parent, width=self.W, height=self.H, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.key, self.selected, self.on_pick = key, selected, on_pick
        self.hover = 0.0
        self._anim = None
        self._fade = 1.0
        self.bind("<ButtonRelease-1>", lambda e: self.on_pick(self.key))
        self.bind("<Enter>", lambda e: self._tween(1.0))
        self.bind("<Leave>", lambda e: self._tween(0.0))
        self._draw()

    def _tween(self, target):
        if self._anim:
            self._anim.cancel()
        start = self.hover

        def frame(t):
            self.hover = start + (target - start) * t
            self._draw()
        self._anim = anim.animate(self, 150, frame)

    def set_fade(self, t):
        self._fade = t
        self._draw()

    def _draw(self):
        # Text items are created once and only recoloured/moved per frame:
        # each preset uses its own fonts, and re-creating text in seven font
        # families every animation frame made fades stutter.
        dim = 0.35 if self.locked_text else 1.0
        f = lambda c: anim.blend(BG, c, self._fade * dim)
        w, h = self.W, self.H
        lift = 2 * self.hover
        ring = PINK if self.selected else anim.blend(BORDER, INK_DIM, self.hover)
        if self.locked_text and not getattr(self, "_lock_items", None):
            self._lock_items = self.create_text(w - 12, 22, anchor="e", font=mono_font(9, "bold"),
                                                text="LOCKED \u00b7 " + self.locked_text)
        if self.locked_text:
            self.coords(self._lock_items, w - 12, 22 - lift)
            self.itemconfigure(self._lock_items, fill=anim.blend(BG, INK, self._fade))
        if not getattr(self, "_items", None):
            self._items = {
                "card": self.create_polygon(0, 0, 0, 0, smooth=True),
                "name": self.create_text(0, 0, anchor="w", font=preset_font(self.key, "display", 15, "bold"),
                                         text=FONT_PRESETS[self.key][0] + ("  \u2713" if self.selected else "")),
                "mono": self.create_text(0, 0, anchor="w", font=preset_font(self.key, "mono", 11, "bold"),
                                         text="01h 59m 42s"),
                "body": self.create_text(0, 0, anchor="w", font=preset_font(self.key, "body", 10),
                                         text="Lock out distractions."),
            }
        it = self._items
        self.coords(it["card"], *rounded_rect_points(2, 2 - lift, w - 2, h - 2 - lift, 10))
        self.itemconfigure(it["card"], fill=f(SURFACE_2), outline=f(ring), width=2 if self.selected else 1)
        for key, y, color in (("name", 24, YELLOW if self.selected else INK), ("mono", 52, CYAN), ("body", 75, INK_DIM)):
            self.coords(it[key], 14, y * TEXT_SCALE - lift)
            self.itemconfigure(it[key], fill=f(color))
        if self.locked_text:
            self.tag_raise(self._lock_items)


class ColorDot(tk.Canvas):
    """A rounded colour swatch that fades with its card."""

    def __init__(self, parent, color, width=40, height=30):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.color = color
        self.set_fade(1.0)

    def set_color(self, color):
        self.color = color
        self.set_fade(1.0)

    def set_fade(self, t):
        w, h = int(self["width"]), int(self["height"])
        self.delete("all")
        self.create_polygon(rounded_rect_points(2, 2, w - 2, h - 2, 8), smooth=True,
                            fill=anim.blend(self["bg"], self.color, t),
                            outline=anim.blend(self["bg"], BORDER_STRONG, t))


class ColorRow(tk.Frame):
    """One custom colour: a swatch, its name and hex code. Click anywhere on
    it to edit."""

    def __init__(self, parent, label, color, on_click):
        super().__init__(parent, bg=parent["bg"], cursor="hand2")
        self.swatch = ColorDot(self, color)
        self.swatch.pack(side="left")
        text = tk.Frame(self, bg=parent["bg"], cursor="hand2")
        text.pack(side="left", padx=(10, 0))
        tk.Label(text, text=label, font=body_font(10), bg=parent["bg"], fg=INK, cursor="hand2").pack(anchor="w")
        tk.Label(text, text=color.upper(), font=mono_font(9), bg=parent["bg"], fg=INK_FAINT,
                 cursor="hand2").pack(anchor="w")
        for w in anim.walk(self):
            w.bind("<ButtonRelease-1>", lambda e: on_click())


class PomodoroRing(tk.Canvas):
    """The Pomodoro countdown: a ring that drains clockwise from the top,
    a pulsing dot riding its end, and the time in the middle. Reads the
    app's timer state every frame; when the phase changes the ring sweeps
    back to full."""

    SIZE = 300

    def __init__(self, parent, app):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self._phase_key = None
        self._refill = 1.0
        self._fade = 1.0
        anim.loop(self, 1600, self._frame)

    def set_fade(self, t):
        self._fade = t

    def _frame(self, pulse):
        st = self.app.pomo
        self.delete("all")
        if not st:
            return
        phase = st["phases"][st["phase_idx"]]
        key = (st["round_idx"], st["phase_idx"])
        if key != self._phase_key:
            if self._phase_key is not None:
                def frame(t):
                    self._refill = t
                anim.animate(self, 700, frame, easing=anim.ease_in_out_cubic)
            self._phase_key = key
        remaining = self.app._pomo_remaining()
        frac = max(0.0, min(1.0, remaining / phase["seconds"])) if phase["seconds"] else 0.0
        shown = frac * self._refill  # _refill sweeps 0 -> 1 right after a phase change
        f = lambda c: anim.blend(BG, c, self._fade)
        fill, _ = accent_colors(phase.get("accent", "pink"))
        c = self.SIZE / 2
        r = c - 22
        self.create_oval(c - r, c - r, c + r, c + r, outline=f(SURFACE_2), width=14)
        if shown > 0.001:
            self.create_arc(c - r, c - r, c + r, c + r, start=90, extent=-min(359.9, 360 * shown),
                            style="arc", outline=f(fill), width=14)
            a = math.radians(90 - 360 * shown)
            hx, hy = c + r * math.cos(a), c - r * math.sin(a)
            k = 9 + 3 * math.sin(2 * math.pi * pulse)
            self.create_oval(hx - k, hy - k, hx + k, hy + k, fill=f(anim.lighten(fill, 0.35)), outline="")
        secs = max(0, math.ceil(remaining))
        h, rem = divmod(secs, 3600)
        m, sec = divmod(rem, 60)
        clock = f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
        paused = st["paused"]
        blink_on = pulse < 0.6
        self.create_text(c, c - 6, text=clock, font=display_font(38, "bold"),
                         fill=f(INK if not paused or blink_on else INK_FAINT))
        self.create_text(c, c + 40, text=("PAUSED" if paused else phase["name"].upper()),
                         font=mono_font(12, "bold"), fill=f(YELLOW if paused else fill))


STOP_SENTENCE = "I am choosing to stop my focus session early."


class StopEarlyDialog(tk.Toplevel):
    """Stopping a Pomodoro early takes typing a sentence out by hand -- the
    friction is the point, so pasting is disabled. .result is True only if
    the sentence was typed exactly."""

    def __init__(self, parent, note=None):
        super().__init__(parent)
        hint_floating(self)
        self.title("Stop early?")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = False

        tk.Label(self, text="STOP EARLY?", font=display_font(15, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 6))
        tk.Label(self, text=note or "Your session will end now and won't count as finished.",
                 font=body_font(10), bg=BG, fg=INK_DIM, wraplength=440, justify="left").pack(
            anchor="w", padx=24)
        quote = card_frame(self, hover=False)
        quote.pack(fill="x", padx=24, pady=(14, 6))
        tk.Label(quote, text=STOP_SENTENCE, font=body_font(12, "italic"), bg=SURFACE, fg=INK,
                 wraplength=420, justify="left").pack(anchor="w", padx=14, pady=12)
        tk.Label(self, text="TYPE IT EXACTLY (PASTING IS OFF)", font=mono_font(9), bg=BG, fg=CYAN).pack(
            anchor="w", padx=24, pady=(10, 4))
        self.var = tk.StringVar()
        self.entry = dialog_entry(self, textvariable=self.var, width=46)
        self.entry.pack(padx=24, ipady=6, fill="x")
        for seq in ("<<Paste>>", "<<PasteSelection>>", "<Control-v>", "<Shift-Insert>", "<Button-2>"):
            self.entry.bind(seq, lambda e: "break")
        self.progress = tk.Label(self, text="", font=mono_font(9), bg=BG, fg=INK_FAINT)
        self.progress.pack(anchor="w", padx=24, pady=(6, 0))
        self.error_label = tk.Label(self, text="", font=body_font(10), bg=BG, fg=PINK)
        self.error_label.pack(padx=24, pady=(4, 0))
        self.var.trace_add("write", self._on_typed)
        self._on_typed()

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=(12, 22))
        make_pill(btn_frame, "Keep going", self._cancel, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(10, "bold"), width=150, height=38).pack(side="left", padx=6)
        small_pill(btn_frame, "Stop session", self._submit, width=140, height=38,
                   font=mono_font(10)).pack(side="left", padx=6)

        self.entry.focus_set()
        finish_dialog(self, parent)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def _on_typed(self, *_):
        typed = self.var.get()
        correct = 0
        for a, b in zip(typed, STOP_SENTENCE):
            if a != b:
                break
            correct += 1
        exact = typed == STOP_SENTENCE
        wrong = len(typed) > correct
        self.progress.config(
            text=f"{correct} / {len(STOP_SENTENCE)} characters" + ("  ·  typo -- fix it to continue" if wrong else ""),
            fg=PINK if wrong else (CYAN if exact else INK_FAINT))
        self.entry.configure(highlightbackground=CYAN if exact else (PINK if wrong else BORDER))

    def _cancel(self):
        self.result = False
        self.destroy()

    def _submit(self):
        if self.var.get() != STOP_SENTENCE:
            snd.play("error")
            self.error_label.config(text="That doesn't match the sentence exactly.")
            anim.shake(self.entry, amplitude=12)
            return
        self.result = True
        self.destroy()


# ---------- dialogs ----------

def finish_dialog(dialog, parent):
    """Shared modal setup: make viewable before grabbing (grab_set on an
    unmapped window raises 'grab failed: window not viewable'), then fade
    the contents in section by section."""
    # Hide (and start fading) before the window maps, so it never flashes
    # fully drawn first.
    stagger_in(dialog.winfo_children(), step=45, duration=300, start=60)
    dialog.transient(parent)
    dialog.wait_visibility()
    dialog.grab_set()


def dialog_entry(parent, **kw):
    return tk.Entry(
        parent, bg=SURFACE_2, fg=INK, insertbackground=INK, relief="flat",
        highlightthickness=1, highlightbackground=BORDER, highlightcolor=CYAN,
        font=body_font(11), **kw,
    )


class PasswordConfirmDialog(tk.Toplevel):
    """Password + a typed literal confirmation. .result is the password, or None.
    Without a password step (Windows, which shows its own UAC prompt next)
    only the confirmation is asked for and .result is ""."""

    def __init__(self, parent, title, summary_lines, confirm_word):
        super().__init__(parent)
        hint_floating(self)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self.confirm_word = confirm_word

        tk.Label(self, text=title.upper(), font=display_font(14, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 8)
        )
        summary = card_frame(self, hover=False)
        summary.pack(fill="x", padx=24, pady=(0, 6))
        for i, line in enumerate(summary_lines):
            tk.Label(summary, text=line, font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left",
                     wraplength=400).pack(anchor="w", padx=14, pady=(10 if i == 0 else 2, 10 if i == len(summary_lines) - 1 else 0))

        if plat.NEEDS_PASSWORD:
            tk.Label(self, text="SUDO PASSWORD", font=mono_font(9), bg=BG, fg=CYAN).pack(
                anchor="w", padx=24, pady=(16, 4)
            )
            self.pw_entry = dialog_entry(self, show="•", width=40)
            self.pw_entry.pack(padx=24, ipady=6, fill="x")
        else:
            self.pw_entry = None
            tk.Label(self, text="Windows will ask for administrator permission next.",
                     font=body_font(10), bg=BG, fg=INK_DIM, justify="left", wraplength=400).pack(
                anchor="w", padx=24, pady=(14, 0)
            )

        tk.Label(self, text=f'TYPE "{confirm_word}" TO CONFIRM', font=mono_font(9), bg=BG, fg=CYAN).pack(
            anchor="w", padx=24, pady=(14, 4)
        )
        self.confirm_var = tk.StringVar()
        self.confirm_entry = dialog_entry(self, width=40, textvariable=self.confirm_var)
        self.confirm_entry.pack(padx=24, ipady=6, fill="x")
        self._matched = False
        self.confirm_var.trace_add("write", self._on_confirm_typed)

        self.error_label = tk.Label(self, text="", font=body_font(10), bg=BG, fg=PINK)
        self.error_label.pack(pady=(10, 0), padx=24)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=(14, 22))
        small_pill(btn_frame, "Cancel", self._cancel, width=110, height=38, font=mono_font(10)).pack(
            side="left", padx=6
        )
        make_pill(
            btn_frame, title, self._submit, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
            font=mono_font(10, "bold"), width=max(160, text_width(title, mono_font(10, "bold")) + 44), height=38,
        ).pack(side="left", padx=6)

        (self.pw_entry or self.confirm_entry).focus_set()
        finish_dialog(self, parent)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def _on_confirm_typed(self, *_):
        matched = self.confirm_var.get() == self.confirm_word
        if matched == self._matched:
            return
        self._matched = matched
        start, end = (BORDER, PINK) if matched else (PINK, BORDER)

        def frame(t):
            self.confirm_entry.configure(highlightbackground=anim.blend(start, end, t))
        anim.animate(self.confirm_entry, 250, frame)

    def _fail(self, message, widget):
        snd.play("error")
        self.error_label.config(text=message)
        anim.pulse(self.error_label, "fg", YELLOW, PINK, 500)
        anim.shake(widget, amplitude=12)
        widget.focus_set()

    def _cancel(self):
        self.result = None
        self.destroy()

    def _submit(self):
        password = self.pw_entry.get() if self.pw_entry is not None else ""
        confirm = self.confirm_entry.get()
        if confirm != self.confirm_word:
            self._fail(f'Confirmation must be exactly "{self.confirm_word}".', self.confirm_entry)
            return
        if not password and self.pw_entry is not None:
            self._fail("Password is required.", self.pw_entry)
            return
        self.result = password
        self.destroy()


class NamePromptDialog(tk.Toplevel):
    def __init__(self, parent, title, label_text):
        super().__init__(parent)
        hint_floating(self)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None

        tk.Label(self, text=label_text, font=body_font(10), bg=BG, fg=INK).pack(
            padx=24, pady=(22, 8), anchor="w"
        )
        self.entry = dialog_entry(self, width=30)
        self.entry.pack(padx=24, ipady=6, fill="x")

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=18)
        small_pill(btn_frame, "Cancel", self._cancel, width=90, height=34).pack(side="left", padx=6)
        make_pill(
            btn_frame, "Save", self._submit, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
            font=mono_font(9, "bold"), width=90, height=34,
        ).pack(side="left", padx=6)

        self.entry.focus_set()
        finish_dialog(self, parent)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def _cancel(self):
        self.result = None
        self.destroy()

    def _submit(self):
        name = self.entry.get().strip()
        if not name:
            snd.play("error")
            anim.shake(self.entry)
            return
        self.result = name
        self.destroy()


QUICK_COLORS = ["#ff2e9a", "#ff6b6b", "#ff8a5b", "#ffd319", "#a3e635", "#4fd1a5", "#2de2e6", "#38bdf8",
                "#6366f1", "#a855f7", "#f5f5f5", "#9ca3af", "#1f2937", "#111111"]


class ColorPickerDialog(tk.Toplevel):
    """Pick a colour: drag in the saturation/brightness square and along the
    hue bar, type a hex code, or click a quick swatch. .result is '#rrggbb',
    or None if cancelled."""

    SV_W, SV_H, RES = 260, 170, 2   # the square is drawn at 1/RES resolution and zoomed
    PAD = 8                         # room around the square so its marker never gets cut off

    def __init__(self, parent, title, initial):
        super().__init__(parent)
        hint_floating(self)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self.initial = initial
        r, g, b = (c / 255 for c in anim.to_rgb(initial))
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r, g, b)
        self._sv_hue = None
        self._typing = False

        tk.Label(self, text=title.upper(), font=display_font(14, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=22, pady=(20, 10))

        self.sv = tk.Canvas(self, width=self.SV_W + 2 * self.PAD, height=self.SV_H + 2 * self.PAD, bg=BG,
                            highlightthickness=0, bd=0, cursor="crosshair")
        self.sv.pack(padx=22 - self.PAD)
        self.hue = tk.Canvas(self, width=self.SV_W, height=18, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self.hue.pack(padx=22, pady=(10, 0))
        hue_img = tk.PhotoImage(width=self.SV_W, height=1)
        hue_img.put("{" + " ".join(anim.rgb_hex(tuple(255 * c for c in colorsys.hsv_to_rgb(x / self.SV_W, 1, 1)))
                                   for x in range(self.SV_W)) + "}", to=(0, 0))
        self._hue_img = hue_img.zoom(1, 18)
        self.hue.create_image(0, 0, image=self._hue_img, anchor="nw")
        self.hue_marker = self.hue.create_rectangle(0, 0, 0, 0, outline="#ffffff", width=2)
        self.sv_image = self.sv.create_image(self.PAD, self.PAD, anchor="nw")
        self.sv_marker = self.sv.create_oval(0, 0, 0, 0, outline="#ffffff", width=2)
        self.sv_marker_in = self.sv.create_oval(0, 0, 0, 0, outline="#000000", width=1)
        for seq in ("<Button-1>", "<B1-Motion>"):
            self.sv.bind(seq, self._on_sv)
            self.hue.bind(seq, self._on_hue)

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=22, pady=(14, 0))
        self.preview = tk.Canvas(row, width=72, height=34, bg=BG, highlightthickness=0, bd=0)
        self.preview.pack(side="left")
        tk.Label(row, text="HEX", font=mono_font(9, "bold"), bg=BG, fg=INK_FAINT).pack(side="left", padx=(14, 6))
        self.hex_var = tk.StringVar()
        self.entry = dialog_entry(row, width=9, textvariable=self.hex_var)
        self.entry.configure(font=mono_font(11))
        self.entry.pack(side="left", ipady=5)
        self.hex_var.trace_add("write", lambda *_: self._on_hex())

        quick = tk.Frame(self, bg=BG)
        quick.pack(padx=22, pady=(14, 0), anchor="w")
        for i, color in enumerate(QUICK_COLORS):
            dot = ColorDot(quick, color, width=26, height=26)
            dot.grid(row=i // 7, column=i % 7, padx=(0, 6), pady=(0, 6))
            dot.bind("<ButtonRelease-1>", lambda e, c=color: self._set_hex(c))

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=(10, 18))
        small_pill(btn_frame, "Cancel", self._cancel, width=90, height=34).pack(side="left", padx=6)
        make_pill(btn_frame, "Use colour", self._submit, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(9, "bold"), width=120, height=34).pack(side="left", padx=6)

        self._redraw(update_entry=True)
        finish_dialog(self, parent)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def color(self):
        return anim.rgb_hex(tuple(255 * c for c in colorsys.hsv_to_rgb(self.h, self.s, self.v)))

    def _render_sv(self):
        """The saturation (x) / brightness (y) square for the current hue."""
        w, h = self.SV_W // self.RES, self.SV_H // self.RES
        rows = []
        for y in range(h):
            v = 1 - y / (h - 1)
            rows.append("{" + " ".join(
                anim.rgb_hex(tuple(255 * c for c in colorsys.hsv_to_rgb(self.h, x / (w - 1), v)))
                for x in range(w)) + "}")
        img = tk.PhotoImage(width=w, height=h)
        img.put(" ".join(rows), to=(0, 0))
        self._sv_img = img.zoom(self.RES, self.RES)
        self.sv.itemconfigure(self.sv_image, image=self._sv_img)
        self._sv_hue = self.h

    def _redraw(self, update_entry=False):
        if self._sv_hue != self.h:
            self._render_sv()
        x, y = self.PAD + self.s * (self.SV_W - 1), self.PAD + (1 - self.v) * (self.SV_H - 1)
        self.sv.coords(self.sv_marker, x - 7, y - 7, x + 7, y + 7)
        self.sv.coords(self.sv_marker_in, x - 5, y - 5, x + 5, y + 5)
        hx = self.h * (self.SV_W - 1)
        self.hue.coords(self.hue_marker, hx - 3, 1, hx + 3, 17)
        color = self.color()
        self.preview.delete("all")
        self.preview.create_polygon(rounded_rect_points(1, 1, 36, 33, 8), smooth=True, fill=self.initial,
                                    outline=BORDER_STRONG)
        self.preview.create_polygon(rounded_rect_points(36, 1, 71, 33, 8), smooth=True, fill=color,
                                    outline=BORDER_STRONG)
        if update_entry:
            self._typing = True
            self.hex_var.set(color.upper())
            self._typing = False

    def _on_sv(self, event):
        self.s = max(0.0, min(1.0, (event.x - self.PAD) / (self.SV_W - 1)))
        self.v = max(0.0, min(1.0, 1 - (event.y - self.PAD) / (self.SV_H - 1)))
        self._redraw(update_entry=True)

    def _on_hue(self, event):
        self.h = max(0.0, min(0.999, event.x / (self.SV_W - 1)))
        self._redraw(update_entry=True)

    def _set_hex(self, color):
        r, g, b = (c / 255 for c in anim.to_rgb(color))
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r, g, b)
        self._redraw(update_entry=True)

    def _on_hex(self):
        if self._typing:
            return
        text = self.hex_var.get().strip()
        if not text.startswith("#"):
            text = "#" + text
        if _HEX_RE.fullmatch(text):
            r, g, b = (c / 255 for c in anim.to_rgb(text.lower()))
            self.h, self.s, self.v = colorsys.rgb_to_hsv(r, g, b)
            self._redraw()

    def _cancel(self):
        self.result = None
        self.destroy()

    def _submit(self):
        text = self.hex_var.get().strip()
        if not text.startswith("#"):
            text = "#" + text
        if not _HEX_RE.fullmatch(text):
            snd.play("error")
            anim.shake(self.entry)
            return
        self.result = text.lower()
        self.destroy()


class SelectionDialog(tk.Toplevel):
    """The mandatory stop between clicking Start Block and the password
    prompt: pick a preset and/or customize the switches. .result is True
    only if the user hit Continue with at least one item selected."""

    def __init__(self, parent, app_vars, domain_vars):
        super().__init__(parent)
        # Built-in plus custom apps, read fresh each time the dialog opens.
        apps, self.dev_keys = all_apps(), dev_tool_keys()
        self.groups = [
            ("GAMES & APPS", [(k, n) for k, n in apps if k not in self.dev_keys], "apps", None),
            ("WEBSITES", all_domains(), "domains", None),
            ("DEV TOOLS", [(k, n) for k, n in apps if k in self.dev_keys], "apps",
             "Off by default -- these are your game-dev tools."),
        ]
        hint_floating(self)
        self.title("Choose what to block")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = False
        self.app = parent
        self.app_vars = app_vars
        self.domain_vars = domain_vars
        self._traces = []

        tk.Label(
            self, text="SELECT WHAT TO BLOCK", font=display_font(15, "bold"), bg=BG, fg=YELLOW,
        ).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(
            self, text="Pick a preset or flip the switches. This is the last step before the password prompt.",
            font=body_font(9), bg=BG, fg=INK_DIM, wraplength=560, justify="left",
        ).pack(anchor="w", padx=26, pady=(0, 14))

        preset_card = card_frame(self)
        preset_card.pack(fill="x", padx=26, pady=(0, 14))
        tk.Label(preset_card, text="PRESETS", font=mono_font(9, "bold"), bg=SURFACE, fg=CYAN).pack(
            anchor="w", padx=14, pady=(12, 6)
        )
        self.presets_row = tk.Frame(preset_card, bg=SURFACE)
        self.presets_row.pack(fill="x", padx=14, pady=(0, 8))
        self._render_presets()
        small_pill(preset_card, "+ Save current as preset", self._on_save_preset, fg=INK).pack(
            anchor="w", padx=14, pady=(0, 12)
        )

        # The switches sit in a scroll area, so the dialog never grows past
        # the screen however many custom apps/sites there are.
        self.switch_area = ScrollableFrame(self, bg=BG)
        self.switch_area.pack(padx=26, anchor="w")
        columns = tk.Frame(self.switch_area.inner, bg=BG)
        columns.pack(anchor="w")
        self.columns = columns
        left = tk.Frame(columns, bg=BG)
        left.pack(side="left", anchor="n", fill="y")
        right = tk.Frame(columns, bg=BG)
        right.pack(side="left", anchor="n", padx=(28, 0))
        self.switch_order = []
        for (title, items, kind, hint), col in zip(self.groups, (left, right, right)):
            self._build_group(col, title, items, kind, hint)

        select_row = tk.Frame(self, bg=BG)
        select_row.pack(pady=(14, 0))
        small_pill(select_row, "Select all", lambda: self._wave(lambda k: True), width=110, height=34).pack(
            side="left", padx=4
        )
        small_pill(select_row, "Defaults", lambda: self._wave(lambda k: k not in self.dev_keys),
                   width=110, height=34).pack(side="left", padx=4)
        small_pill(select_row, "Select none", lambda: self._wave(lambda k: False), width=110, height=34).pack(
            side="left", padx=4
        )

        self.error_label = tk.Label(self, text="", font=body_font(9), bg=BG, fg=PINK)
        self.error_label.pack(pady=(10, 0), padx=26)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=(8, 24))
        small_pill(btn_frame, "Cancel", self._cancel, width=110, height=38, font=mono_font(10)).pack(
            side="left", padx=6
        )
        make_pill(
            btn_frame, "Continue", self._continue, bg=PINK, fg=ON_PINK,
            hover_bg=PINK_HOVER, font=mono_font(10, "bold"), width=140, height=38,
        ).pack(side="left", padx=6)

        self._fit_switch_area()
        finish_dialog(self, parent)
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._continue())
        for seq, notches in (("<Button-4>", -1), ("<Button-5>", 1)):
            self.bind(seq, lambda e, n=notches: self.switch_area.scroll_by(n))
        self.bind("<MouseWheel>", lambda e: self.switch_area.scroll_by(-1 if e.delta > 0 else 1))

    def _fit_switch_area(self):
        """Size the scroll area to its content, capped so the whole dialog
        stays on screen; the scrollbar only shows when it's needed."""
        self.update_idletasks()
        need_h = self.columns.winfo_reqheight()
        rest = self.winfo_reqheight() - self.switch_area.winfo_reqheight()
        avail = max(220, self.winfo_screenheight() - 110 - rest)
        area = self.switch_area
        area.canvas.configure(width=self.columns.winfo_reqwidth(), height=min(need_h, avail))
        if need_h <= avail:
            area.vsb.pack_forget()

    def _build_group(self, parent, title, items, kind, hint):
        variables = self.app_vars if kind == "apps" else self.domain_vars
        group = tk.Frame(parent, bg=BG)
        group.pack(anchor="w", pady=(0, 14), fill="x")
        header = tk.Frame(group, bg=BG)
        header.pack(anchor="w", fill="x", pady=(0, 4))
        tk.Label(header, text=title, font=mono_font(11, "bold"), bg=BG, fg=CYAN).pack(side="left")
        count = tk.Label(header, text="", font=mono_font(9), bg=BG, fg=INK_FAINT)
        count.pack(side="left", padx=(10, 0))
        if hint:
            tk.Label(group, text=hint, font=body_font(9), bg=BG, fg=INK_FAINT).pack(anchor="w", pady=(0, 4))
        accent = YELLOW if title == "DEV TOOLS" else (CYAN if kind == "domains" else PINK)

        def update_count(*_):
            if anim._alive(count):
                on = sum(variables[k].get() for k, _ in items)
                count.config(text=f"{on}/{len(items)}", fg=INK if on else INK_FAINT)
        for key, label in items:
            sw = ToggleSwitch(group, label, variables[key], accent=accent)
            sw.pack(anchor="w")
            self.switch_order.append((key, variables[key]))
            self._traces.append((variables[key], variables[key].trace_add("write", update_count)))
        update_count()

    def destroy(self):
        for var, tid in self._traces:
            try:
                var.trace_remove("write", tid)
            except (tk.TclError, ValueError):
                pass
        self._traces = []
        super().destroy()

    def _wave(self, want):
        """Set every switch, rippling top-to-bottom instead of all at once.
        Scheduled on the main window, so a wave still finishes (it only sets
        variables) even if this dialog closes mid-way."""
        delay = 0
        for key, var in self.switch_order:
            value = bool(want(key))
            if var.get() != value:
                self.app.after(delay, var.set, value)
                delay += 35

    def _render_presets(self):
        for w in self.presets_row.winfo_children():
            w.destroy()
        presets = load_presets()
        if not presets:
            tk.Label(
                self.presets_row, text="(none saved yet -- customize below, then save one)",
                font=body_font(9), bg=SURFACE, fg=INK_FAINT,
            ).pack(side="left")
            return
        for name in presets:
            small_pill(self.presets_row, name, lambda n=name: self._load_preset(n), fg=INK).pack(
                side="left", padx=(0, 6), pady=2
            )

    def _load_preset(self, name):
        preset = load_presets().get(name)
        if not preset:
            return
        chosen = set(preset.get("apps", [])) | set(preset.get("domains", []))
        self._wave(lambda k: k in chosen)

    def _on_save_preset(self):
        dlg = NamePromptDialog(self, "Save Preset", "Name this preset:")
        self.wait_window(dlg)
        if not dlg.result:
            return
        presets = load_presets()
        presets[dlg.result] = {
            "apps": [k for k, v in self.app_vars.items() if v.get()],
            "domains": [k for k, v in self.domain_vars.items() if v.get()],
        }
        save_presets(presets)
        self._render_presets()
        stagger_in(self.presets_row.winfo_children(), step=40, duration=260, from_color=SURFACE)

    def _cancel(self):
        self.result = False
        self.destroy()

    def _continue(self):
        if not any(v.get() for v in self.app_vars.values()) and not any(
            v.get() for v in self.domain_vars.values()
        ):
            self.error_label.config(text="Choose at least one app or website to block.")
            snd.play("error")
            anim.shake(self.error_label)
            return
        self.result = True
        self.destroy()


def short_path(path, limit=56):
    """'/home/me/Games/x/very/long/path' -> '~/Games/x/ver...ong/path'."""
    home = os.path.expanduser("~")
    if path.startswith(home + "/"):
        path = "~" + path[len(home):]
    if len(path) <= limit:
        return path
    keep = limit - 3
    return path[: keep // 3] + "..." + path[-(keep - keep // 3):]


def guess_app_name(path):
    """'Aseprite_1.3.15.4-x64.AppImage' -> 'Aseprite'."""
    base = os.path.basename(path)
    base = re.sub(r"(?i)\.(appimage|sh|x86_64|bin|run)$", "", base)
    base = re.split(r"[_\-. ](?=v?\d|x64|x86|linux|amd64)", base, maxsplit=1)[0]
    base = sanitize_app_name(base.replace("_", " ").replace("-", " ").strip())
    return base[:1].upper() + base[1:] if base else "My app"


class AddAppDialog(tk.Toplevel):
    """Pick an app to block -- a program file, an installed Flatpak, or
    something running right now -- then name it and say what it is.
    .result is the new custom-app dict, or None."""

    SOURCES = ([("path", "Program file"), ("running", "Running now")] if plat.IS_WINDOWS
               else [("path", "Program file"), ("flatpak", "Flatpak"), ("running", "Running now")])

    def __init__(self, parent, existing):
        super().__init__(parent)
        hint_floating(self)
        self.title("Add an app")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self.existing = existing
        self.source = "path"
        self.kind = "game"
        self.path_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.choices = []  # (label, source, target) behind the list
        self._ready = False  # no panel fade until the dialog's own fade-in is set up

        tk.Label(self, text="ADD AN APP", font=display_font(15, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 4))
        tk.Label(self, text="It'll show up in Start Block's switches and get blocked like the built-in apps.",
                 font=body_font(9), bg=BG, fg=INK_DIM).pack(anchor="w", padx=24, pady=(0, 12))

        src_row = tk.Frame(self, bg=BG)
        src_row.pack(anchor="w", padx=24, pady=(0, 10))
        self.source_chips = []
        for key, label in self.SOURCES:
            chip = small_pill(src_row, label, lambda k=key: self._pick_source(k), height=32)
            chip.pack(side="left", padx=(0, 6))
            self.source_chips.append((chip, key))

        self.panel = card_frame(self, hover=False)
        self.panel.pack(fill="x", padx=24)

        tk.Label(self, text="NAME", font=mono_font(9), bg=BG, fg=CYAN).pack(anchor="w", padx=24, pady=(14, 4))
        self.name_entry = dialog_entry(self, textvariable=self.name_var, width=40)
        self.name_entry.pack(fill="x", padx=24, ipady=6)

        tk.Label(self, text="WHAT IS IT?", font=mono_font(9), bg=BG, fg=CYAN).pack(
            anchor="w", padx=24, pady=(14, 4))
        kind_row = tk.Frame(self, bg=BG)
        kind_row.pack(anchor="w", padx=24)
        self.kind_chips = []
        for key, label in CUSTOM_KINDS:
            chip = small_pill(kind_row, label, lambda k=key: self._pick_kind(k), height=32)
            chip.pack(side="left", padx=(0, 6))
            self.kind_chips.append((chip, key))
        tk.Label(self, text="Dev tools start switched off in Start Block, like Godot and Aseprite.",
                 font=body_font(9), bg=BG, fg=INK_FAINT).pack(anchor="w", padx=24, pady=(4, 0))

        self.error_label = tk.Label(self, text="", font=body_font(10), bg=BG, fg=PINK, wraplength=460)
        self.error_label.pack(padx=24, pady=(10, 0))
        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=(10, 22))
        small_pill(btns, "Cancel", self._cancel, width=110, height=38, font=mono_font(10)).pack(side="left", padx=6)
        make_pill(btns, "Add app", self._submit, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(10, "bold"), width=140, height=38).pack(side="left", padx=6)

        self._pick_kind("game")
        self._pick_source("path")
        finish_dialog(self, parent)
        self._ready = True
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._submit())

    # ---- choosing ----

    def _style_chips(self, chips, selected, accent=CYAN, on=ON_CYAN):
        for chip, key in chips:
            if key == selected:
                chip.set_colors(accent, on, anim.lighten(accent, 0.2))
            else:
                chip.set_colors(SURFACE_2, INK_DIM, BORDER)

    def _pick_kind(self, kind):
        self.kind = kind
        fill, ink = accent_colors(KIND_ACCENTS[kind])
        self._style_chips(self.kind_chips, kind, fill, ink)

    def _pick_source(self, source):
        self.source = source
        self._style_chips(self.source_chips, source)
        self.error_label.config(text="")
        for w in self.panel.winfo_children():
            w.destroy()
        self.listbox = None
        if source == "path":
            tk.Label(self.panel, text="PROGRAM FILE", font=mono_font(9), bg=SURFACE, fg=CYAN).pack(
                anchor="w", padx=14, pady=(12, 4))
            row = tk.Frame(self.panel, bg=SURFACE)
            row.pack(fill="x", padx=14, pady=(0, 6))
            dialog_entry(row, textvariable=self.path_var, width=34).pack(side="left", fill="x", expand=True, ipady=5)
            small_pill(row, "Browse...", self._browse, height=32, fg=INK).pack(side="left", padx=(8, 0))
            tk.Label(self.panel, text=("e.g. a game's .exe in Program Files or your user folder."
                                       if plat.IS_WINDOWS else
                                       "e.g. an AppImage or game in your home folder, /opt or /usr/games."),
                     font=body_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=14, pady=(0, 12))
        else:
            if source == "flatpak":
                items = [(f"{name}   ({app_id})", "flatpak", app_id) for app_id, name in installed_flatpaks()]
                empty = "No other Flatpak apps are installed."
            else:
                items = [(f"{name}   ({short_path(exe, 44)})", "path", exe) for name, exe in running_programs()]
                empty = "Nothing blockable is running right now. Open the app, then come back."
            self.choices = items
            if not items:
                tk.Label(self.panel, text=empty, font=body_font(10), bg=SURFACE, fg=INK_FAINT).pack(
                    anchor="w", padx=14, pady=16)
            else:
                self.listbox = tk.Listbox(
                    self.panel, height=min(7, len(items)), bg=SURFACE, fg=INK, selectbackground=CYAN,
                    selectforeground=ON_CYAN, highlightthickness=0, bd=0, activestyle="none",
                    font=body_font(10), exportselection=False)
                for label, _, _ in items:
                    self.listbox.insert("end", "  " + label)
                self.listbox.pack(fill="x", padx=10, pady=10)
                self.listbox.bind("<<ListboxSelect>>", self._on_list_pick)
            if source == "running":
                small_pill(self.panel, "Refresh", lambda: self._pick_source("running"), height=28).pack(
                    anchor="e", padx=14, pady=(0, 10))
        if self._ready:
            # Only after the dialog's first fade-in has captured the real
            # colours -- fading earlier would make it capture hidden ones.
            anim.fade_in(self.panel, BG, 250)

    def _browse(self):
        extra = {"filetypes": [("Programs", "*.exe")]} if plat.IS_WINDOWS else {}
        path = filedialog.askopenfilename(parent=self, title="Choose the program to block",
                                          initialdir=os.path.expanduser("~"), **extra)
        if path:
            path = os.path.normpath(path)   # Tk hands back C:/... on Windows
            self.path_var.set(path)
            if not self.name_var.get().strip():
                self.name_var.set(guess_app_name(path))

    def _on_list_pick(self, _event=None):
        sel = self.listbox.curselection() if self.listbox else ()
        if not sel:
            return
        label, _, target = self.choices[sel[0]]
        self.name_var.set(sanitize_app_name(label.split("   (")[0]) if self.source == "flatpak"
                          else guess_app_name(target))

    # ---- finishing ----

    def _fail(self, message):
        snd.play("error")
        self.error_label.config(text=message)
        anim.shake(self.error_label, amplitude=12)

    def _submit(self):
        if self.source == "path":
            source, target = "path", self.path_var.get().strip()
            problem = check_custom_path(target)
        else:
            sel = self.listbox.curselection() if self.listbox else ()
            if not sel:
                self._fail("Pick an app from the list first.")
                return
            _, source, target = self.choices[sel[0]]
            problem = check_flatpak_id(target) if source == "flatpak" else check_custom_path(target)
        if problem:
            self._fail(problem)
            return
        if any(a["source"] == source and a["target"] == target for a in self.existing):
            self._fail("You've already added that app.")
            return
        name = sanitize_app_name(self.name_var.get())
        if not name:
            self._fail("Give it a name (letters, numbers and spaces).")
            return
        key = make_custom_key(name, {a["key"] for a in self.existing} | {k for k, _ in all_apps()})
        self.result = {"key": key, "name": name, "kind": self.kind, "source": source, "target": target}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


QUICK_SITES = [("Reddit", "reddit.com"), ("Twitch", "twitch.tv"), ("X / Twitter", "x.com, twitter.com"),
               ("TikTok", "tiktok.com"), ("Facebook", "facebook.com"), ("Netflix", "netflix.com")]


class AddWebsiteDialog(tk.Toplevel):
    """Name a website and give one or more addresses (URLs are fine -- they
    are trimmed to the domain). .result is the new custom-site dict, or None."""

    def __init__(self, parent, existing):
        super().__init__(parent)
        hint_floating(self)
        self.title("Add a website")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self.existing = existing
        taken = {d for site in existing for d in site["domains"]} | {d for ds in DOMAIN_GROUPS.values() for d in ds}
        self.taken = taken
        self.name_var = tk.StringVar()
        self.addr_var = tk.StringVar()

        tk.Label(self, text="ADD A WEBSITE", font=display_font(15, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 4))
        tk.Label(self, text="Blocked like the built-in sites \u2014 in every browser, through /etc/hosts.",
                 font=body_font(9), bg=BG, fg=INK_DIM).pack(anchor="w", padx=24, pady=(0, 12))

        quick = [(n, a) for n, a in QUICK_SITES if not {normalize_domain(x) for x in a.split(",")} & taken]
        if quick:
            tk.Label(self, text="QUICK PICKS", font=mono_font(9), bg=BG, fg=CYAN).pack(anchor="w", padx=24, pady=(0, 4))
            row = tk.Frame(self, bg=BG)
            row.pack(anchor="w", padx=24, pady=(0, 6))
            for name, addr in quick:
                small_pill(row, name, lambda n=name, a=addr: (self.name_var.set(n), self.addr_var.set(a)),
                           height=30).pack(side="left", padx=(0, 6))

        tk.Label(self, text="NAME", font=mono_font(9), bg=BG, fg=CYAN).pack(anchor="w", padx=24, pady=(10, 4))
        dialog_entry(self, textvariable=self.name_var, width=40).pack(fill="x", padx=24, ipady=6)
        tk.Label(self, text="ADDRESS (SEPARATE SEVERAL WITH COMMAS)", font=mono_font(9), bg=BG, fg=CYAN).pack(
            anchor="w", padx=24, pady=(12, 4))
        self.addr_entry = dialog_entry(self, textvariable=self.addr_var, width=40)
        self.addr_entry.pack(fill="x", padx=24, ipady=6)
        self.preview = tk.Label(self, text="", font=mono_font(9), bg=BG, fg=INK_FAINT, wraplength=440,
                                justify="left")
        self.preview.pack(anchor="w", padx=24, pady=(6, 0))
        self.error_label = tk.Label(self, text="", font=body_font(10), bg=BG, fg=PINK, wraplength=440)
        self.error_label.pack(padx=24, pady=(8, 0))
        self.addr_var.trace_add("write", lambda *_: self._update_preview())
        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=(10, 22))
        small_pill(btns, "Cancel", self._cancel, width=110, height=38, font=mono_font(10)).pack(side="left", padx=6)
        make_pill(btns, "Add website", self._submit, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(10, "bold"), width=150, height=38).pack(side="left", padx=6)
        self._update_preview()
        self.addr_entry.focus_set()
        finish_dialog(self, parent)
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._submit())

    def _parse(self):
        """([valid domains], [(text, problem)])"""
        good, bad = [], []
        for part in re.split(r"[,\s]+", self.addr_var.get()):
            if not part:
                continue
            d = normalize_domain(part)
            problem = check_domain(d) or ("Already blocked by FocusLock." if d in self.taken else None)
            if problem:
                bad.append((part, problem))
            elif d not in good:
                good.append(d)
        return good, bad

    def _update_preview(self):
        self.error_label.config(text="")
        good, bad = self._parse()
        if not good and not bad:
            self.preview.config(text="e.g. reddit.com \u2014 www.reddit.com is blocked too.", fg=INK_FAINT)
        elif bad:
            self.preview.config(text=f"\u2717 {bad[0][0]}: {bad[0][1]}", fg=PINK)
        else:
            blocked = [x for d in good for x in site_domains(d)]
            self.preview.config(text="Will block: " + ", ".join(blocked), fg=CYAN)
        if good and not self.name_var.get().strip():
            first = good[0].split(".")[-2] if good[0].count(".") >= 1 else good[0]
            self.name_var.set(first[:1].upper() + first[1:])

    def _submit(self):
        good, bad = self._parse()
        if bad or not good:
            snd.play("error")
            self.error_label.config(text=bad[0][1] if bad else "Enter at least one website address.")
            anim.shake(self.error_label, amplitude=12)
            return
        name = sanitize_app_name(self.name_var.get()) or good[0]
        key = "w" + make_custom_key(name, set())[1:]
        existing_keys = {s["key"] for s in self.existing} | set(DOMAIN_GROUPS)
        n = 2
        base = key
        while key in existing_keys:
            key, n = f"{base}_{n}", n + 1
        self.result = {"key": key, "name": name, "domains": [x for d in good for x in site_domains(d)]}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class TemplateDialog(tk.Toplevel):
    """Name a template made from the LOCK tab's current setup, and give it
    optional starter tasks. .result is (name, [tasks]) or None."""

    def __init__(self, parent, summary_lines):
        super().__init__(parent)
        hint_floating(self)
        self.title("Save as template")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        tk.Label(self, text="SAVE AS TEMPLATE", font=display_font(15, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 6))
        for line in summary_lines:
            tk.Label(self, text=line, font=body_font(10), bg=BG, fg=INK_DIM, wraplength=440, justify="left").pack(
                anchor="w", padx=24)
        tk.Label(self, text="NAME", font=mono_font(9, "bold"), bg=BG, fg=CYAN).pack(anchor="w", padx=24, pady=(14, 4))
        self.entry = dialog_entry(self, width=32)
        self.entry.pack(padx=24, ipady=6, fill="x")
        tk.Label(self, text="STARTER TASKS (OPTIONAL, ONE PER LINE)", font=mono_font(9, "bold"), bg=BG,
                 fg=CYAN).pack(anchor="w", padx=24, pady=(14, 4))
        self.tasks = tk.Text(self, height=5, width=40, bg=SURFACE_2, fg=INK, insertbackground=INK, relief="flat",
                             highlightthickness=1, highlightbackground=BORDER, highlightcolor=CYAN,
                             font=body_font(10), wrap="word")
        self.tasks.pack(padx=24, fill="x")
        tk.Label(self, text="They're added to the session's task list when the lock starts.", font=body_font(9),
                 bg=BG, fg=INK_FAINT).pack(anchor="w", padx=24, pady=(4, 0))
        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=18)
        small_pill(btns, "Cancel", self._cancel, width=90, height=34).pack(side="left", padx=6)
        make_pill(btns, "Save", self._submit, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(9, "bold"), width=90, height=34).pack(side="left", padx=6)
        self.entry.focus_set()
        finish_dialog(self, parent)
        self.entry.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def _cancel(self):
        self.result = None
        self.destroy()

    def _submit(self):
        name = " ".join(self.entry.get().split())[:TEMPLATE_NAME_MAX]
        if not name:
            snd.play("error")
            anim.shake(self.entry)
            return
        tasks = [" ".join(line.split())[:TASK_TEXT_MAX] for line in self.tasks.get("1.0", "end").splitlines()]
        self.result = (name, [t for t in tasks if t][:TASK_MAX])
        self.destroy()


class RestoreConfirmDialog(tk.Toplevel):
    """Confirm replacing the current data with a backup. .result is True to restore."""

    def __init__(self, parent, created, parts):
        super().__init__(parent)
        hint_floating(self)
        self.title("Restore this backup?")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = False
        self.protocol("WM_DELETE_WINDOW", self._no)

        tk.Label(self, text="RESTORE THIS BACKUP?", font=display_font(15, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 6))
        tk.Label(self, text=f"Made {created}.", font=body_font(10), bg=BG, fg=INK).pack(anchor="w", padx=24)
        box = card_frame(self, hover=False)
        box.pack(fill="x", padx=24, pady=(14, 6))
        tk.Label(box, text="IT REPLACES YOUR CURRENT", font=mono_font(9, "bold"), bg=SURFACE, fg=CYAN).pack(
            anchor="w", padx=14, pady=(12, 4))
        tk.Label(box, text=", ".join(parts).capitalize() + ".", font=body_font(10), bg=SURFACE, fg=INK_DIM,
                 wraplength=400, justify="left").pack(anchor="w", padx=14)
        tk.Frame(box, bg=SURFACE, height=10).pack()
        tk.Label(self, text="Your current data is saved first (in ~/.config/focuslock/backups), so you can "
                            "go back. A lock that's running isn't affected.",
                 font=body_font(9), bg=BG, fg=INK_FAINT, wraplength=440, justify="left").pack(
            anchor="w", padx=24, pady=(6, 0))
        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=(16, 22))
        small_pill(btns, "Cancel", self._no, width=120, height=38, font=mono_font(10)).pack(side="left", padx=6)
        make_pill(btns, "Restore", self._yes, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(10, "bold"), width=150, height=38).pack(side="left", padx=6)
        finish_dialog(self, parent)
        self.bind("<Return>", lambda e: self._yes())
        self.bind("<Escape>", lambda e: self._no())

    def _yes(self):
        self.result = True
        self.destroy()

    def _no(self):
        self.result = False
        self.destroy()


class ScanPermissionDialog(tk.Toplevel):
    """Asked once, on first launch: may FocusLock look through this
    computer's installed apps for things to suggest blocking? .result is
    True (allow) or False (not now -- the Apps tab keeps an Allow button)."""

    def __init__(self, parent):
        super().__init__(parent)
        hint_floating(self)
        self.title("Find distractions for you?")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = False
        self.protocol("WM_DELETE_WINDOW", self._no)

        tk.Label(self, text="FIND DISTRACTIONS FOR YOU?", font=display_font(15, "bold"), bg=BG, fg=YELLOW).pack(
            anchor="w", padx=24, pady=(22, 6))
        tk.Label(self, text="FocusLock can look through the apps on this computer and suggest games, chat "
                            "and video apps to block, in the Apps tab.",
                 font=body_font(10), bg=BG, fg=INK, wraplength=440, justify="left").pack(anchor="w", padx=24)
        box = card_frame(self, hover=False)
        box.pack(fill="x", padx=24, pady=(14, 6))
        tk.Label(box, text="IT WOULD READ", font=mono_font(9, "bold"), bg=SURFACE, fg=CYAN).pack(
            anchor="w", padx=14, pady=(12, 4))
        for line in (("Your Start menu shortcuts", "Your Steam library's list of games") if plat.IS_WINDOWS else
                     ("Your app menu entries (including Flatpak and Snap apps)",
                      "AppImages and Games folders in your home folder",
                      "Your Steam library's list of games")):
            tk.Label(box, text="\u2022  " + line, font=body_font(10), bg=SURFACE, fg=INK_DIM).pack(
                anchor="w", padx=14)
        tk.Frame(box, bg=SURFACE, height=10).pack()
        tk.Label(self, text="It only reads lists of apps \u2014 nothing leaves this computer, and nothing "
                            "gets blocked unless you press Add. You can turn it off any time in the Apps tab.",
                 font=body_font(9), bg=BG, fg=INK_FAINT, wraplength=440, justify="left").pack(
            anchor="w", padx=24, pady=(6, 0))
        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=(16, 22))
        small_pill(btns, "Not now", self._no, width=120, height=38, font=mono_font(10)).pack(side="left", padx=6)
        make_pill(btns, "Allow scan", self._yes, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(10, "bold"), width=150, height=38).pack(side="left", padx=6)
        finish_dialog(self, parent)
        self.bind("<Return>", lambda e: self._yes())
        self.bind("<Escape>", lambda e: self._no())

    def _yes(self):
        self.result = True
        self.destroy()

    def _no(self):
        self.result = False
        self.destroy()


# ---------- main window ----------

TABS = [("lock", "LOCK"), ("pomodoro", "POMODORO"), ("stats", "STATS"), ("badges", "BADGES"), ("apps", "APPS"),
        ("settings", "SETTINGS")]
KIND_ACCENTS = {"game": "pink", "dev": "yellow", "other": "cyan"}
SCAN_CATEGORY_ACCENTS = {scanner.GAME: "pink", scanner.CHAT: "cyan", scanner.MEDIA: "yellow"}
POMO_KINDS = [("Study", "pink"), ("Code", "cyan"), ("Break", "yellow")]


def format_hms(secs):
    secs = max(0, int(round(secs)))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

DURATION_CHIPS = [
    ("25m", 0, 0, 25), ("1h", 0, 1, 0), ("2h", 0, 2, 0), ("4h", 0, 4, 0),
    ("1 day", 1, 0, 0), ("2 days", 2, 0, 0), ("1 week", 7, 0, 0),
]


class FocusLockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        hint_floating(self, "utility")
        self.title("FocusLock")
        if plat.IS_WINDOWS:
            icon = os.path.join(SELF_DIR, "icon.ico")
            if os.path.exists(icon):
                self.iconbitmap(default=icon)   # default= covers dialogs too
        self.geometry("800x880")
        self.minsize(620, 620)
        self.resizable(True, True)

        dev = dev_tool_keys()
        settings = load_settings()
        if "distraction_log_since" not in settings:
            # "Clean lock" XP only counts locks the distraction log could have seen.
            settings["distraction_log_since"] = int(time.time())
            save_settings(settings)
        set_custom_colors(load_custom_colors())
        apply_font_preset(settings.get("font_preset", "retro"))
        apply_text_size(settings.get("text_size", "default"))
        saved_theme = settings.get("theme", "dark")
        apply_theme(saved_theme if saved_theme in _THEMES else "dark")
        self.app_vars = {key: tk.BooleanVar(value=key not in dev) for key, _ in all_apps()}
        self.domain_vars = {key: tk.BooleanVar(value=True) for key, _ in all_domains()}
        self.days_var = tk.IntVar(value=2)
        self.hours_var = tk.IntVar(value=0)
        self.minutes_var = tk.IntVar(value=0)
        self.intent_var = tk.StringVar()
        self._template_id = None       # the template last loaded on the LOCK tab
        self._template_tasks = []      # its starter tasks, added when the lock starts

        # Traces live as long as the app; the views they update come and go,
        # so the callbacks check the target widgets still exist.
        for var in list(self.app_vars.values()) + list(self.domain_vars.values()):
            var.trace_add("write", lambda *_: self._update_selection_summary())
        for var in (self.days_var, self.hours_var, self.minutes_var):
            var.trace_add("write", lambda *_: self._update_duration_ui())

        self._busy = False
        self._toast = None
        self._tick_id = None
        self._was_locked = None
        self.scroller = None
        self.sound_btn = None
        self.tabbar = None
        self.tab = "lock"
        self._ticks = 0

        # Pomodoro: the saved plan (empty until built), the editor's
        # fields, and the running timer's state (None when idle).
        self.pomo_plan = load_pomo_plan()
        self.pomo = None
        self._pomo_after = None
        self.pomo_name_var = tk.StringVar()
        self.pomo_h, self.pomo_m, self.pomo_s = tk.IntVar(value=0), tk.IntVar(value=0), tk.IntVar(value=0)
        self.pomo_accent = "pink"
        self.pomo_rounds_var = tk.IntVar(value=self.pomo_plan["rounds"])
        self.pomo_rounds_var.trace_add("write", lambda *_: self._pomo_rounds_changed())

        # Focus sounds (ambient loops); remembers the last sound and volume,
        # but never starts playing by itself.
        amb = load_settings().get("ambient", {})
        self.ambient = ambient.AmbientPlayer()
        self.ambient.volume = float(amb.get("volume", 0.5))
        self.ambient_last = amb.get("sound", "rain")

        # Entertainment scan: results of the latest scan (None until one runs).
        self.scan_result = None
        self._scan_running = False


        snd.enabled = load_settings().get("sound", True)
        # Synthesizing the sounds takes a moment the first time; do it off
        # the main thread so startup isn't delayed. It only writes files.
        threading.Thread(target=self._prepare_sounds, daemon=True).start()

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)
        # Views are built into body; the tab bar sits above it and survives
        # view changes (it's only rebuilt on theme changes).
        self.body = tk.Frame(self.container)
        self.body.pack(side="bottom", fill="both", expand=True)

        for seq, notches in (("<Button-4>", -1), ("<Button-5>", 1)):
            self.bind_all(seq, lambda e, n=notches: self._on_wheel(e, n))
        self.bind_all("<MouseWheel>", lambda e: self._on_wheel(e, -1 if e.delta > 0 else 1))
        self.bind("<Control-t>", lambda e: self.toggle_theme())
        for i, (key, _) in enumerate(TABS, start=1):
            self.bind(f"<Control-Key-{i}>", lambda e, k=key: self.select_tab(k))
        self.bind("<Control-Tab>", lambda e: self._cycle_tab())
        self.bind("<Control-m>", lambda e: self.toggle_sound())
        self.bind("<question>", self._on_help_key)
        self.bind("<F1>", lambda e: self.show_shortcuts())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._apply_chrome_colors()
        self.refresh(intro=True)
        self.after(1600, self._sync_badges)
        self.after(1200, self._scan_on_startup)
        self.after(2500, self._maybe_show_recap)
        self.after(4000, self._check_rewards)
        self.after(1500, self._ensure_logger)

    @staticmethod
    def _prepare_sounds():
        try:
            snd.ensure_sounds()
        except OSError:
            pass  # no writable cache: play() will just stay silent

    # ---------- chrome ----------

    def _apply_chrome_colors(self):
        self.configure(bg=BG)
        self.container.configure(bg=BG)
        self.body.configure(bg=BG)
        if self.tabbar is not None:
            self.tabbar.destroy()
        self.tabbar = TabBar(self.container, TABS, self.tab, self.select_tab)
        self.tabbar.pack(side="top", fill="x", before=self.body)
        self._place_sound_btn()

    def _place_sound_btn(self):
        # Created after (and placed on top of) container so it isn't hidden
        # beneath it -- place()'d siblings stack in creation order.
        if self.sound_btn is not None:
            self.sound_btn.destroy()
        self.sound_btn = small_pill(self, "SOUND ON" if snd.enabled else "SOUND OFF", self.toggle_sound,
                                    height=30, fg=INK if snd.enabled else INK_FAINT, sound=None)
        self.sound_btn.place(relx=1.0, x=-22, y=(TabBar.H - 30) // 2 - 1, anchor="ne")
        raise_window(self.sound_btn)
        if self.tabbar is not None and anim._alive(self.tabbar):
            self.tabbar.fit()

    def toggle_sound(self, play=True):
        snd.enabled = not snd.enabled
        settings = load_settings()
        settings["sound"] = snd.enabled
        save_settings(settings)
        if play:
            snd.play("toggle_on")  # silent when just muted
        self._place_sound_btn()
        if getattr(self, "sound_var", None) is not None and self.sound_var.get() != snd.enabled:
            self.sound_var.set(snd.enabled)

    def _pick_theme(self, key, swatch=None):
        if self._refuse_locked("theme", key, dict(THEME_NAMES)[key]):
            return
        origin = None
        if swatch is not None and anim._alive(swatch):
            origin = (swatch.winfo_rootx() - self.winfo_rootx() + 75, swatch.winfo_rooty() - self.winfo_rooty() + 37)
        self.set_theme(key, origin)

    def toggle_theme(self):
        """Ctrl+T: next theme in the list."""
        hours, level = self._focus_hours(), self._level()
        keys = [k for k, _ in THEME_NAMES if not self._lock_label("theme", k, hours, level) or k == current_theme_name]
        self.set_theme(keys[(keys.index(current_theme_name) + 1) % len(keys)])

    def set_theme(self, key, origin=None):
        """Switch themes: the old UI melts into its background, the new
        background spreads out as a circle from origin, then the rebuilt UI
        fades in."""
        if self._busy or key == current_theme_name or key not in _THEMES:
            return
        settings = load_settings()
        settings["theme"] = key
        save_settings(settings)
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        self._busy = True
        old_bg, new_bg = BG, _THEMES[key]["BG"]
        w, h = self.winfo_width(), self.winfo_height()
        ox, oy = origin or (w - 60, TabBar.H // 2)

        def reveal():
            cover = tk.Canvas(self, bg=old_bg, highlightthickness=0, bd=0)
            cover.place(x=0, y=0, relwidth=1, relheight=1)
            raise_window(cover)
            radius = math.hypot(max(ox, w - ox), max(oy, h - oy))
            circle = cover.create_oval(ox, oy, ox, oy, fill=new_bg, outline="")

            def grow(t):
                r = radius * t
                cover.coords(circle, ox - r, oy - r, ox + r, oy + r)

            def swap():
                top = self._scroll_top()
                apply_theme(key)
                self._apply_chrome_colors()
                self.refresh(intro=False)
                self._restore_scroll(top)
                raise_window(cover)
                cover.configure(bg=new_bg)
                self._busy = False
                self.after(30, cover.destroy)
            anim.animate(cover, 420, grow, easing=anim.ease_in_out_cubic, on_done=swap)

        anim.fade_to(self.container, old_bg, 160, on_done=reveal)

    def select_tab(self, key):
        if self._busy or key == self.tab:
            return
        self.tab = key
        snd.play("tab")
        self.tabbar.select(key)
        self.refresh(intro=True)

    def _cycle_tab(self):
        keys = [k for k, _ in TABS]
        self.select_tab(keys[(keys.index(self.tab) + 1) % len(keys)])
        return "break"  # keep Tk from also moving keyboard focus

    def toast(self, message, kind="info", duration_ms=3600, sound=None):
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        sound = sound or ("error" if kind == "error" else None)
        if sound:
            snd.play(sound)
        accent = {"info": CYAN, "success": PINK, "warn": YELLOW, "error": PINK}[kind]
        self._toast = Toast(self, message, accent, duration_ms)

    def _on_wheel(self, event, notches):
        widget = event.widget
        if not isinstance(widget, tk.Misc) or widget.winfo_toplevel() is not self:
            return
        if self.scroller is not None and anim._alive(self.scroller):
            self.scroller.scroll_by(notches)

    def _on_close(self):
        if self._busy:
            self.toast("Hang on -- finishing up. Closing now could leave things half-applied.", "warn")
            return
        if self.pomo and not self._pomo_stop_early(
                "Closing FocusLock ends your running Pomodoro, and it won't count as finished."):
            return
        self.ambient.stop()
        self.destroy()

    # ---------- view switching ----------

    def refresh(self, intro=True):
        for w in self.body.winfo_children():
            w.destroy()
        self.countdown_label = None
        self.duration_preview = None
        self.selection_summary = None
        self.chips = []
        unlock_at = read_file(UNLOCK_AT_FILE)
        self._was_locked = unlock_at is not None
        self.after_idle(lambda: responsive_wraps(self.body))
        if self.tab == "stats":
            self._build_stats_view(intro)
        elif self.tab == "badges":
            self._build_badges_view(intro)
        elif self.tab == "pomodoro":
            self._build_pomodoro_view(intro)
        elif self.tab == "apps":
            self._build_apps_view(intro)
        elif self.tab == "settings":
            self._build_settings_view(intro)
        elif unlock_at:
            self._build_locked_view(unlock_at, intro)
        else:
            self._build_setup_view(intro)
        if self._tick_id is not None:
            self.after_cancel(self._tick_id)
        self._tick_id = self.after(1000, self.refresh_tick)

    # ---------- background attempt logger ----------
    # Locks started before the distraction log existed have wrappers that only
    # show a notification. focuslock_watch.py turns those notifications into
    # log entries; it runs as its own process so it keeps going while this
    # window is closed (and exits when the lock ends).

    LOGGER_UNIT = "focuslock-attempt-logger.service"
    LOGGER_UNIT_PATH = os.path.join("~/.config/systemd/user", "focuslock-attempt-logger.service")

    def _ensure_logger(self):
        if not plat.HAS_ATTEMPT_WATCHER or read_file(UNLOCK_AT_FILE) is None:
            return
        try:
            if os.path.exists(os.path.expanduser(self.LOGGER_UNIT_PATH)):
                subprocess.Popen(["systemctl", "--user", "start", self.LOGGER_UNIT], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:   # its own session: closing this window doesn't stop it
                subprocess.Popen(watcher_command(), cwd=os.path.expanduser("~"),
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
        except OSError:
            pass   # logging is a nice-to-have

    @staticmethod
    def _logger_running():
        """True if the background logger holds its single-instance lock."""
        import fcntl
        try:
            fd = os.open(focuslock_watch.lock_path(), os.O_RDWR)
        except OSError:
            return False
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except OSError:
            return True
        finally:
            os.close(fd)

    def _set_logger_autostart(self, on):
        """Install (or remove) a systemd user service that starts the logger
        at login whenever a lock is active."""
        path = os.path.expanduser(self.LOGGER_UNIT_PATH)
        try:
            if on:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write("[Unit]\nDescription=FocusLock - log blocked-app attempts while the app is closed\n"
                            f"ConditionPathExists={UNLOCK_AT_FILE}\n\n[Service]\n"
                            "ExecStart=" + " ".join(f'"{a}"' for a in watcher_command()) + "\n"
                            "Restart=on-failure\nRestartSec=30\n\n[Install]\nWantedBy=default.target\n")
                for cmd in (["daemon-reload"], ["enable", self.LOGGER_UNIT]):
                    subprocess.run(["systemctl", "--user", *cmd], capture_output=True, timeout=10)
                self._ensure_logger()
            else:
                subprocess.run(["systemctl", "--user", "disable", self.LOGGER_UNIT], capture_output=True, timeout=10)
                if os.path.exists(path):
                    os.remove(path)
                subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as e:
            self.toast(f"Couldn't change that: {e}", "error")
            return False
        return True

    def refresh_tick(self):
        self._tick_id = self.after(1000, self.refresh_tick)
        if self._busy:
            return  # the lock state is mid-change; the busy flow refreshes itself
        self._ticks += 1
        if self._ticks % 60 == 0:
            self._sync_badges()  # focus-time badges can be earned mid-lock
        if self._ticks % 5 == 0:
            self._update_goal()
        if self._ticks % 3 == 0:
            self._update_distractions()
        if self._ticks % 120 == 0:
            self._ensure_logger()
        if self._ticks % 30 == 0:
            self._check_challenges()
            self._check_level()
            self._check_rewards()
        # Cheap poll: if the timer fired while the GUI was open, flip views.
        still_locked = read_file(UNLOCK_AT_FILE) is not None
        if still_locked != self._was_locked:
            was_locked = self._was_locked
            self._was_locked = still_locked
            if self.tab == "lock":
                self.refresh(intro=True)
            if was_locked and not still_locked:
                done, total = task_counts(load_tasks()["tasks"])
                extra = f" You checked off {done} of {total} task{'s' if total != 1 else ''}." if total else ""
                self.toast("Block finished -- everything is unblocked again. Nice work." + extra, "success", 6500,
                           sound="chime")
            return
        if self.tab != "lock":
            return
        if still_locked:
            self._update_countdown(pulse=True)
        else:
            self._update_duration_ui()

    # ---------- settings view ----------

    def _scroll_top(self):
        """How far down the current page is scrolled, in pixels."""
        if self.scroller is not None and anim._alive(self.scroller):
            return self.scroller.canvas.canvasy(0)
        return 0.0

    def _restore_scroll(self, top):
        """After a rebuild, scroll back to the same spot (e.g. the card being
        edited). The new page grows over several layout passes (wrapping
        rows, flowing grids), so keep re-applying the offset for ~1.5 s as
        its height changes -- and stop as soon as the user scrolls."""
        if not top:
            return
        state = {"set": None}

        def go(tries):
            scroller = self.scroller
            if scroller is None or not anim._alive(scroller):
                return
            canvas = scroller.canvas
            bbox = canvas.bbox("all")
            height = bbox[3] - bbox[1] if bbox else 0
            view = canvas.winfo_height()
            if view > 1 and height > view:
                current = canvas.canvasy(0)
                if state["set"] is not None and abs(current - state["set"]) > 2:
                    return   # the user has scrolled since; leave it alone
                target = min(top, height - view)
                if abs(current - target) > 1:
                    canvas.configure(scrollregion=bbox)
                    canvas.yview_moveto(target / height)
                state["set"] = canvas.canvasy(0)
            if tries:
                self.after(50, lambda: go(tries - 1))
        self.after(30, lambda: go(30))

    def _restyle(self, change):
        """Apply a change to the look (colours or fonts) and rebuild the UI
        in place: fade out, change, rebuild, fade in -- keeping the scroll
        position so the card being edited stays in view."""
        if self._busy:
            return
        self._busy = True
        top = self._scroll_top()

        def swap():
            change()
            apply_theme(current_theme_name)
            self._apply_chrome_colors()
            self.refresh(intro=False)
            self._restore_scroll(top)
            self._busy = False
        anim.fade_to(self.container, BG, 140, on_done=swap)

    def _build_settings_view(self, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        c = self.scroller.inner

        title = tk.Label(c, text="Settings", font=display_font(26, "bold"), bg=BG, fg=YELLOW)
        title.pack(pady=(26, 4))
        subtitle = tk.Label(c, text="MAKE FOCUSLOCK YOURS", font=mono_font(10), bg=BG, fg=INK_FAINT)
        subtitle.pack(pady=(0, 20))
        content = tk.Frame(c, bg=BG)
        content.pack(fill="x", padx=44)

        self._build_theme_card(content)
        self._build_custom_colors_card(content)
        self._build_fonts_card(content)
        self._build_celebration_card(content)
        self._build_sound_card(content)
        self._build_backup_card(content)
        self._build_website_logging_card(content)
        row = tk.Frame(content, bg=BG)
        row.pack(pady=(14, 40))
        small_pill(row, "Keyboard shortcuts  ( ? )", self.show_shortcuts, height=30).pack()

        if intro:
            stagger_in([subtitle] + content.winfo_children(), step=80, duration=420, start=150)
        else:
            stagger_in([c], step=0, duration=320)

    def _build_theme_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "THEME")
        grid = FlowFrame(card, bg=SURFACE, gap=8)
        grid.pack(fill="x", padx=16, pady=(0, 16))
        hours, level = self._focus_hours(), self._level()
        for key, label in THEME_NAMES:
            grid.add(ThemeSwatch(grid, key, label, key == current_theme_name, self._pick_theme,
                                 locked_text=self._lock_label("theme", key, hours, level)))

    def _build_custom_colors_card(self, parent):
        colors = load_custom_colors()
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "CUSTOM COLORS")
        using = current_theme_name == "custom"
        tk.Label(card, text=("These colours make up your Custom theme. Click one to change it -- borders and "
                             "dimmed text are worked out from them automatically."),
                 font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 12))

        grid = FlowFrame(card, bg=SURFACE, gap=10)
        grid.pack(fill="x", padx=16)
        for key, label in CUSTOM_COLOR_KEYS:
            grid.add(ColorRow(grid, label, colors[key], lambda k=key, l=label: self._edit_custom_color(k, l)))

        problems = []
        if contrast(colors["INK"], colors["BG"]) < 4.5:
            problems.append("text on the background")
        if contrast(colors["INK"], colors["SURFACE"]) < 4.5:
            problems.append("text on cards")
        if problems:
            tk.Label(card, text="Heads up: " + " and ".join(problems) + " may be hard to read -- try a lighter "
                     "or darker Text colour.", font=body_font(9), bg=SURFACE, fg=YELLOW, justify="left",
                     wraplength=560).pack(anchor="w", padx=16, pady=(12, 0))

        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=(14, 16))
        if not using:
            make_pill(row, "Use Custom theme", lambda: self.set_theme("custom"), bg=PINK, fg=ON_PINK,
                      hover_bg=PINK_HOVER, font=mono_font(9, "bold"), width=170, height=34).pack(side="left")
        else:
            tk.Label(row, text="✓ Custom theme in use", font=mono_font(9, "bold"), bg=SURFACE,
                     fg=PINK).pack(side="left")
        small_pill(row, "Reset", self._reset_custom_colors, height=34).pack(side="right")
        if current_theme_name != "custom":
            small_pill(row, f"Copy {dict(THEME_NAMES)[current_theme_name]}", self._copy_theme_to_custom,
                       height=34).pack(side="right", padx=(0, 8))

    def _edit_custom_color(self, key, label):
        if self._busy:
            return
        colors = load_custom_colors()
        dlg = ColorPickerDialog(self, label, colors[key])
        self.wait_window(dlg)
        if not dlg.result or dlg.result == colors[key]:
            return
        colors[key] = dlg.result
        self._save_custom_colors(colors)

    def _save_custom_colors(self, colors):
        settings = load_settings()
        settings["custom_colors"] = colors
        save_settings(settings)
        self._restyle(lambda: set_custom_colors(colors))

    def _reset_custom_colors(self):
        self._save_custom_colors(default_custom_colors())

    def _copy_theme_to_custom(self):
        """Start the custom colours from the theme in use."""
        theme = _THEMES[current_theme_name]
        self._save_custom_colors({key: theme[key] for key, _ in CUSTOM_COLOR_KEYS})
        self.toast(f"Custom colours now start from {dict(THEME_NAMES)[current_theme_name]}.", "info")

    def _build_fonts_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "FONTS")
        grid = FlowFrame(card, bg=SURFACE, gap=8)
        grid.pack(fill="x", padx=16, pady=(0, 16))
        hours = self._focus_hours()
        for key in FONT_PRESETS:
            grid.add(FontPresetCard(grid, key, key == current_font_preset, self._pick_font_preset,
                                    locked_text=self._lock_label("font", key, hours)))
        tk.Label(card, text="TEXT SIZE", font=mono_font(9, "bold"), bg=SURFACE, fg=INK_FAINT).pack(
            anchor="w", padx=16, pady=(0, 6))
        sizes = FlowFrame(card, bg=SURFACE, gap=6)
        sizes.pack(fill="x", padx=16, pady=(0, 16))
        for key, label, _ in TEXT_SIZES:
            on = key == current_text_size
            sizes.add(small_pill(sizes, label, lambda k=key: self._pick_text_size(k), height=30,
                                 bg=PINK if on else SURFACE_2, fg=ON_PINK if on else INK,
                                 hover_bg=PINK_HOVER if on else BORDER))

    def _pick_font_preset(self, key):
        if key == current_font_preset or self._busy or self._refuse_locked("font", key, FONT_PRESETS[key][0]):
            return
        snd.play("click")
        settings = load_settings()
        settings["font_preset"] = key
        save_settings(settings)
        self._restyle(lambda: apply_font_preset(key))

    def _pick_text_size(self, key):
        if key == current_text_size or self._busy:
            return
        snd.play("click")
        settings = load_settings()
        settings["text_size"] = key
        save_settings(settings)
        self._restyle(lambda: apply_text_size(key))

    CELEBRATIONS = [("classic", "Confetti")] + [(r[2], r[3]) for r in REWARDS if r[1] == "celebration"]

    def _celebration_style(self):
        style = load_settings().get("celebration", "classic")
        if style not in dict(self.CELEBRATIONS) or self._lock_label("celebration", style):
            return "classic"
        return style

    def _build_celebration_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "LOCK-IN CELEBRATION")
        tk.Label(card, text="What plays when a lock snaps shut. More styles unlock with focus hours.",
                 font=body_font(10), bg=SURFACE, fg=INK_DIM).pack(anchor="w", padx=16, pady=(0, 10))
        row = FlowFrame(card, bg=SURFACE, gap=6)
        row.pack(fill="x", padx=16, pady=(0, 10))
        current, hours = self._celebration_style(), self._focus_hours()
        for key, label in self.CELEBRATIONS:
            lock = self._lock_label("celebration", key, hours)
            on = key == current
            row.add(small_pill(row, f"{label} \u00b7 {lock}" if lock else label,
                               lambda k=key: self._pick_celebration(k), height=30,
                               bg=PINK if on else (anim.blend(SURFACE, SURFACE_2, 0.5) if lock else SURFACE_2),
                               fg=ON_PINK if on else (INK_FAINT if lock else INK),
                               hover_bg=PINK_HOVER if on else BORDER))
        small_pill(card, "Preview", lambda: self._preview_celebration(current), height=30, fg=CYAN).pack(
            anchor="w", padx=16, pady=(0, 14))

    def _pick_celebration(self, key):
        if self._busy or self._refuse_locked("celebration", key, dict(self.CELEBRATIONS)[key]):
            return
        settings = load_settings()
        settings["celebration"] = key
        save_settings(settings)
        snd.play("toggle_on")
        self._restyle(lambda: None)
        self.after(500, lambda: self._preview_celebration(key))

    def _preview_celebration(self, key):
        if self._busy:
            self.after(300, lambda: self._preview_celebration(key))
            return
        self._busy = True
        Overlay(self).celebrate("LOCKED IN", ["(preview -- nothing was locked)"],
                                on_reveal=lambda: self._finish_busy(refresh=False), style=key)

    def _build_sound_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "SOUND")
        var = self.sound_var = tk.BooleanVar(value=snd.enabled)

        def changed(*_):
            # Uses its own var: after a rebuild self.sound_var is a newer one.
            if var.get() != snd.enabled:
                self.toggle_sound(play=False)   # the switch already played its own sound
        var.trace_add("write", changed)
        ToggleSwitch(card, "Sound effects", var, width=300).pack(anchor="w", padx=16, pady=(0, 4))
        tk.Label(card, text="Clicks, chimes and badge sounds. Focus sounds have their own volume on the LOCK tab.",
                 font=body_font(9), bg=SURFACE, fg=INK_FAINT, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 14))

    def _build_backup_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "BACKUP & RESTORE")
        tk.Label(card, text=("Save everything -- settings, theme, history, streaks, badges, Pomodoro, presets, and "
                             "the apps and websites you added -- to one file. Restore it here or on another "
                             "computer. Neither touches a lock that's running."),
                 font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 10))
        last = load_settings().get("last_backup")
        try:
            when = fmt_date(datetime.fromisoformat(last), "%-d %b %Y, %H:%M") if last else None
        except (TypeError, ValueError):
            when = None
        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=(0, 16))
        make_pill(row, "Back up\u2026", self._on_backup, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(9, "bold"), width=130, height=34).pack(side="left")
        small_pill(row, "Restore\u2026", self._on_restore, height=34).pack(side="left", padx=(8, 0))
        tk.Label(row, text=f"Last backup: {when}" if when else "No backup yet", font=mono_font(9), bg=SURFACE,
                 fg=INK_FAINT).pack(side="right")

    def _build_website_logging_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "DISTRACTION LOGGING")
        if not plat.HAS_ATTEMPT_WATCHER:
            # Windows: the blocker itself logs each attempt; no site logger yet.
            for text, fg in (("\u2713 Apps: every try to open a blocked app is logged, even while FocusLock "
                              "is closed.", PINK),
                             ("Websites: blocked, but attempts aren't counted on Windows yet.", INK_DIM)):
                tk.Label(card, text=text, font=body_font(10, "bold"), bg=SURFACE, fg=fg, justify="left",
                         wraplength=560).pack(anchor="w", padx=16, pady=(0, 6))
            return
        locked = read_file(UNLOCK_AT_FILE) is not None
        if not locked:
            apps, apps_color = "Apps: logged whenever you try to open one during a lock.", INK
        elif self._logger_running():
            apps, apps_color = "\u2713 Apps: logged \u2014 even while FocusLock is closed.", PINK
        else:
            apps, apps_color = "Apps: the background logger isn't running; it starts with FocusLock.", YELLOW
        state, color = self._website_logging_state()
        for text, fg in ((apps, apps_color), ("Websites: " + state if not state.startswith("\u2713")
                                               else "\u2713 Websites: " + state[2:], color)):
            tk.Label(card, text=text, font=body_font(10, "bold"), bg=SURFACE, fg=fg, justify="left",
                     wraplength=560).pack(anchor="w", padx=16, pady=(0, 6))
        tk.Label(card, text=("Built into the lock: during a lock, blocked websites point at a small FocusLock "
                             "logger on this computer instead of nowhere. When you try to open one -- in any "
                             "browser -- it notes which blocked site it was and closes the connection, so the "
                             "site stays blocked. Nothing else is recorded, and it stops when the lock ends."),
                 font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(4, 10))
        var = tk.BooleanVar(value=os.path.exists(os.path.expanduser(self.LOGGER_UNIT_PATH)))

        def changed(*_):
            if not self._set_logger_autostart(var.get()):
                return
            self.toast("The background logger will start when you log in (during a lock)." if var.get()
                       else "The background logger won't start at login any more.", "info", 4000)
        var.trace_add("write", changed)
        ToggleSwitch(card, "Start the background logger when I log in", var, width=380).pack(
            anchor="w", padx=16, pady=(0, 2))
        tk.Label(card, text=("Only matters for locks started before this update -- newer locks log apps by "
                             "themselves. Without it, logging resumes after a restart once you open FocusLock."),
                 font=body_font(9), bg=SURFACE, fg=INK_FAINT, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 14))

    @staticmethod
    def _website_logging_state():
        if read_file(UNLOCK_AT_FILE) is None:
            return "Starts automatically with your next lock -- no setup, works in every browser.", CYAN
        hosts = read_file(HOSTS_FILE) or ""
        if f"\n{SITELOG_ADDR} " not in "\n" + hosts:
            return ("Your current lock started before website logging existed, so it begins with your next "
                    "lock. Blocked apps are already being logged."), YELLOW
        try:
            active = subprocess.run(["systemctl", "is-active", "--quiet", "focuslock-sitelog.service"],
                                    timeout=3).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            active = False
        if active:
            return "\u2713 On -- attempts to open blocked websites are being counted.", PINK
        return ("The logger isn't running right now, so website attempts aren't counted (the sites are "
                "still blocked). It starts again with your next lock."), YELLOW

    def _on_backup(self):
        if self._busy:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Save FocusLock backup", defaultextension=".json",
            initialdir=os.path.expanduser("~"), initialfile=f"focuslock-backup-{date.today().isoformat()}.json",
            filetypes=[("FocusLock backup", "*.json"), ("All files", "*")])
        if not path:
            return
        try:
            backup = write_backup(path)
        except OSError as e:
            self.toast(f"Couldn't save the backup: {e.strerror or e}", "error")
            return
        settings = load_settings()
        settings["last_backup"] = backup["created"]
        save_settings(settings)
        self.toast(f"Backed up to {short_path(path)}.", "success", 4500, sound="chime")
        if self.tab == "settings":
            self._restyle(lambda: None)   # refresh "Last backup", keeping the scroll position

    def _on_restore(self):
        if self._busy:
            return
        if self.pomo:
            self.toast("Finish or stop your Pomodoro before restoring a backup.", "warn")
            return
        path = filedialog.askopenfilename(
            parent=self, title="Restore FocusLock backup", initialdir=os.path.expanduser("~"),
            filetypes=[("FocusLock backup", "*.json"), ("All files", "*")])
        if not path:
            return
        try:
            backup = read_backup(path)
        except ValueError as e:
            self.toast(str(e), "error", 5000)
            return
        try:
            created = fmt_date(datetime.fromisoformat(backup.get("created", "")), "%-d %b %Y at %H:%M")
        except (TypeError, ValueError):
            created = "at an unknown time"
        parts = [BACKUP_FILES[n][2] for n in BACKUP_FILES if n in backup["files"]]
        if "distractions" in backup["files"]:
            parts.append("distraction log")
        dlg = RestoreConfirmDialog(self, created, parts)
        self.wait_window(dlg)
        if not dlg.result:
            return
        try:
            safety_backup()
            restore_backup(backup)
        except OSError as e:
            self.toast(f"Couldn't restore: {e.strerror or e}", "error")
            return
        self._reload_user_data()
        self.toast("Backup restored.", "success", 4000, sound="chime")

    def _reload_user_data(self):
        """Pick up data that was just replaced on disk (after a restore)."""
        settings = load_settings()
        snd.enabled = settings.get("sound", True)
        amb = settings.get("ambient", {})
        self.ambient.set_volume(float(amb.get("volume", self.ambient.volume)))
        self.ambient_last = amb.get("sound", self.ambient_last)
        self.pomo_plan = load_pomo_plan()
        self.pomo_rounds_var.set(self.pomo_plan["rounds"])
        self._sync_app_vars()
        self._sync_domain_vars()
        self._sync_badges(announce=False)
        theme = settings.get("theme", "dark")

        def change():
            set_custom_colors(load_custom_colors())
            apply_font_preset(settings.get("font_preset", "retro"))
            apply_text_size(settings.get("text_size", "default"))
            apply_theme(theme if theme in _THEMES else "dark")
        self._restyle(change)

    # ---------- setup (unlocked) view ----------

    def _build_setup_view(self, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        c = self.scroller.inner

        title = tk.Label(c, text="FocusLock", font=display_font(30, "bold"), bg=BG, fg=YELLOW)
        title.pack(pady=(26, 6))
        subtitle = tk.Label(c, text="NOT CURRENTLY ACTIVE", font=mono_font(10), bg=BG, fg=INK_FAINT)
        subtitle.pack(pady=(0, 10))
        self._build_level_strip(c)

        content = tk.Frame(c, bg=BG)
        content.pack(fill="x", padx=44)

        self._build_streak_card(content, intro)
        self._build_goal_card(content, intro)
        self._build_templates_card(content)
        self._build_duration_card(content)
        self._build_intent_card(content)
        self._build_ambient_card(content)

        self.selection_summary = tk.Label(content, text="", font=mono_font(9), bg=BG, fg=INK_FAINT)
        self.selection_summary.pack(pady=(14, 12))
        self._update_selection_summary()

        start_row = tk.Frame(content, bg=BG)
        start_row.pack(pady=8)
        start = make_pill(
            start_row, "Start Block", self._on_start_block, bg=PINK, fg=ON_PINK,
            hover_bg=PINK_HOVER, font=mono_font(13, "bold"), width=250, height=56,
        )
        start.pack()
        start.breathe()

        tk.Label(
            content, text="NO EARLY UNLOCK ONCE STARTED — ONLY THE TIMER LIFTS IT",
            font=mono_font(8), bg=BG, fg=INK_FAINT,
        ).pack(pady=(20, 6))
        tk.Label(content, text="Press ? for keyboard shortcuts",
                 font=mono_font(8), bg=BG, fg=INK_FAINT).pack(
            pady=(0, 40)
        )

        sections = [subtitle] + content.winfo_children()
        if intro:
            anim.typewriter(title, "FocusLock", ms_per_char=70, delay_ms=120)
            stagger_in(sections, step=80, duration=420, start=200)
        else:
            stagger_in([c], step=0, duration=320)

    def _build_streak_card(self, parent, intro):
        stats = load_stats()
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "STREAK")
        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=(0, 14))
        cells = [
            ("DAY STREAK", stats.get("streak", 0), PINK),
            ("LONGEST", stats.get("longest_streak", 0), YELLOW),
            ("SESSIONS", stats.get("total_sessions", 0), CYAN),
        ]
        for i, (caption, value, color) in enumerate(cells):
            cell = tk.Frame(row, bg=SURFACE)
            cell.pack(side="left", expand=True, fill="x")
            number = tk.Label(cell, text=str(value), font=display_font(26, "bold"), bg=SURFACE, fg=color)
            number.pack()
            tk.Label(cell, text=caption, font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack()
            if intro and value:
                def count(t, label=number, n=value):
                    label.config(text=str(round(n * t)))
                number.config(text="0")
                anim.animate(number, 900 + 150 * i, count, delay_ms=450 + 120 * i)

    def _build_history_card(self, parent, intro):
        locked_days = locked_days_from_history(load_history())
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "ACTIVITY")
        weeks = Heatmap.WEEKS
        today = date.today()
        hover_label = tk.Label(card, text="", font=body_font(9), bg=SURFACE, fg=INK_FAINT)

        week_end = today + timedelta(days=6 - today.weekday())
        range_start = week_end - timedelta(days=weeks * 7 - 1)
        n_locked = sum(1 for dd in locked_days if range_start <= dd <= today)
        default_text = f"{n_locked} of the last {weeks * 7} days locked  ·  hover a day for details"

        def on_hover(text):
            if anim._alive(hover_label):
                hover_label.config(text=text or default_text, fg=INK if text else INK_FAINT)

        Heatmap(card, locked_days, on_hover=on_hover, intro=intro).pack(padx=16, pady=(0, 6), anchor="w")
        hover_label.config(text=default_text)
        hover_label.pack(anchor="w", padx=16, pady=(0, 14))

    # ---------- stats view ----------

    def _build_stats_view(self, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        c = self.scroller.inner

        title = tk.Label(c, text="Your Stats", font=display_font(26, "bold"), bg=BG, fg=YELLOW)
        title.pack(pady=(26, 4))
        history = load_history()
        st = compute_stats(history)
        stats = load_stats()
        subtitle = tk.Label(c, text=f"{st['sessions']} SESSION(S) SO FAR", font=mono_font(10),
                            bg=BG, fg=INK_FAINT)
        subtitle.pack(pady=(0, 20))

        content = tk.Frame(c, bg=BG)
        content.pack(fill="x", padx=44)
        self._build_total_hours_card(content, intro)

        if not st["sessions"]:
            card = card_frame(content)
            card.pack(fill="x", pady=8)
            tk.Label(card, text="No sessions yet.", font=body_font(13), bg=SURFACE, fg=INK).pack(pady=(26, 4))
            tk.Label(card, text="Start your first lock and your stats will show up here.",
                     font=body_font(10), bg=SURFACE, fg=INK_DIM).pack()
            make_pill(card, "Go to Lock", lambda: self.select_tab("lock"), bg=PINK, fg=ON_PINK,
                      hover_bg=PINK_HOVER, font=mono_font(10, "bold"), width=160, height=40).pack(pady=(16, 26))
        else:
            recap = card_frame(content)
            recap.pack(fill="x", pady=8)
            row = tk.Frame(recap, bg=SURFACE)
            row.pack(fill="x", padx=16, pady=14)
            tk.Label(row, text="WEEKLY RECAP", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
            small_pill(row, "This week so far", lambda: self._show_recap(this_week=True), height=30,
                       fg=INK).pack(side="right")
            make_pill(row, "Last week", lambda: self._show_recap(), bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                      font=mono_font(10, "bold"), width=120, height=30).pack(side="right", padx=(0, 6))
            self._build_overview_card(content, st, stats, intro)
            self._build_calendar_card(content, intro)
            self._build_history_card(content, intro)
            self._build_charts_card(content, st, intro)
            self._build_top_blocked_card(content, st, intro)
            self._build_recent_card(content, st)
        # Shown even without lock history (e.g. Pomodoro-only days count toward
        # the goal), but only with something to show when there's none.
        has_sessions = bool(st["sessions"])
        goals = load_goals()
        if has_sessions or goals["minutes"] or goals["met"]:
            self._build_goal_stats_card(content, intro)
        if has_sessions or load_attempts():
            self._build_distraction_stats_card(content, intro)
        self._build_pomo_stats_card(content, intro)
        if has_sessions or load_pomo_history():
            self._build_export_card(content)

        tk.Frame(content, bg=BG, height=40).pack()
        if intro:
            stagger_in([subtitle] + content.winfo_children(), step=80, duration=420, start=150)
        else:
            stagger_in([c], step=0, duration=320)

    def _build_overview_card(self, parent, st, stats, intro):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "OVERVIEW")
        grid = tk.Frame(card, bg=SURFACE)
        grid.pack(fill="x", padx=16, pady=(0, 12))
        tiles = [
            ("LOCKED TIME", st["focus_seconds"], format_hours, PINK),
            ("SESSIONS", st["sessions"], lambda v: str(round(v)), CYAN),
            ("LONGEST LOCK", st["longest_seconds"],
             lambda v: format_hours(v) if st["longest_seconds"] else "—", YELLOW),
            ("BEST STREAK", stats.get("longest_streak", 0), lambda v: f"{round(v)}d", PINK),
        ]
        for i, (caption, value, fmt, color) in enumerate(tiles):
            grid.columnconfigure(i, weight=1, uniform="tile")
            tile = tk.Frame(grid, bg=SURFACE)
            tile.grid(row=0, column=i, sticky="ew")
            number = tk.Label(tile, text=fmt(value), font=display_font(20, "bold"), bg=SURFACE, fg=color)
            number.pack()
            tk.Label(tile, text=caption, font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack()
            if intro:
                count_up(number, value, fmt, duration=1000 + 120 * i, delay=400 + 110 * i)
        if st["sessions"] > st["timed_sessions"]:
            tk.Label(
                card, text="Older sessions didn't record exact times, so focus time and longest lock "
                           "only count sessions started after this update.",
                font=body_font(9), bg=SURFACE, fg=INK_FAINT, wraplength=620, justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_pomo_stats_card(self, parent, intro):
        ps = pomo_stats(load_pomo_history())
        if not ps["sessions"]:
            return
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "POMODORO")
        grid = tk.Frame(card, bg=SURFACE)
        grid.pack(fill="x", padx=16, pady=(0, 14))
        tiles = [
            ("FINISHED", ps["completed"], lambda v: str(round(v)), PINK),
            ("ROUNDS", ps["rounds"], lambda v: str(round(v)), YELLOW),
            ("TIMED", ps["seconds"], lambda v: format_span(v, False), CYAN),
            ("STOPPED EARLY", ps["stopped_early"], lambda v: str(round(v)), INK_DIM),
        ]
        for i, (caption, value, fmt, color) in enumerate(tiles):
            grid.columnconfigure(i, weight=1, uniform="pomo")
            tile = tk.Frame(grid, bg=SURFACE)
            tile.grid(row=0, column=i, sticky="ew")
            number = tk.Label(tile, text=fmt(value), font=display_font(20, "bold"), bg=SURFACE, fg=color)
            number.pack()
            tk.Label(tile, text=caption, font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack()
            if intro:
                count_up(number, value, fmt, duration=900 + 100 * i, delay=500 + 100 * i)

    def _build_charts_card(self, parent, st, intro):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "SESSIONS PER WEEK")
        week_labels = [d.strftime("%d %b") for d in st["week_starts"]]
        BarChart(card, week_labels, st["weekly_sessions"], PINK,
                 highlight=len(week_labels) - 1, intro=intro).pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(card, text="Each bar is a week, starting Monday. The bright one is this week.",
                 font=body_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(0, 10))

        card_title(card, "WHEN YOU LOCK IN")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        BarChart(card, days, st["by_weekday"], CYAN, highlight=date.today().weekday(),
                 intro=intro).pack(fill="x", padx=16, pady=(0, 6))
        busiest = max(range(7), key=lambda i: st["by_weekday"][i])
        tk.Label(card, text=f"Sessions by the day they started. Your most locked-in day: {days[busiest]}.",
                 font=body_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_top_blocked_card(self, parent, st, intro):
        if not st["top_blocked"]:
            return
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "MOST BLOCKED")
        app_labels, domain_labels, dev = dict(all_apps()), dict(all_domains()), dev_tool_keys()
        rows = []
        for key, count in st["top_blocked"]:
            if key in domain_labels:
                rows.append((domain_labels[key], count, CYAN))
            else:
                rows.append((app_labels.get(key, key), count, YELLOW if key in dev else PINK))
        HBarList(card, rows, intro=intro).pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(card, text="How many sessions blocked each one.", font=body_font(9),
                 bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_recent_card(self, parent, st):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "RECENT SESSIONS")
        table = tk.Frame(card, bg=SURFACE)
        table.pack(fill="x", padx=16, pady=(0, 14))
        table.columnconfigure(3, weight=1)
        for row, s in enumerate(st["recent"]):
            start = date.fromisoformat(s["start"])
            bounds = session_bounds(s)
            length = format_span(bounds[1] - bounds[0], False) if bounds else "—"
            n_blocked = len(s.get("apps", [])) + len(s.get("domains", []))
            intent = s.get("intent") or ""
            cells = [
                (start.strftime("%a %d %b"), mono_font(10), INK),
                (length, mono_font(10), CYAN),
                (f"{n_blocked} blocked", mono_font(9), INK_DIM),
                (intent or "no focus note", body_font(10), INK if intent else INK_FAINT),
            ]
            for col, (text, font, color) in enumerate(cells):
                tk.Label(table, text=text, font=font, bg=SURFACE, fg=color, anchor="w",
                         wraplength=320 if col == 3 else 0, justify="left").grid(
                    row=row, column=col, sticky="w", padx=(0, 18), pady=4)

    def _build_duration_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "BLOCK FOR")

        chip_row = tk.Frame(card, bg=SURFACE)
        chip_row.pack(fill="x", padx=16, pady=(0, 12))
        self.chips = []
        for label, d, h, m in DURATION_CHIPS:
            chip = small_pill(chip_row, label, lambda d=d, h=h, m=m: self._set_duration(d, h, m), height=30)
            chip.pack(side="left", padx=(0, 6))
            self.chips.append((chip, (d, h, m)))

        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16)

        def duration_spin(var, lo, hi, caption):
            tk.Spinbox(
                row, from_=lo, to=hi, textvariable=var, width=4,
                bg=SURFACE_2, fg=INK, buttonbackground=SURFACE_2, insertbackground=INK,
                relief="flat", highlightthickness=1, highlightbackground=BORDER,
                highlightcolor=CYAN, font=body_font(12), justify="center",
            ).pack(side="left", ipady=4)
            tk.Label(row, text=caption, font=mono_font(10), bg=SURFACE, fg=CYAN).pack(side="left", padx=(6, 16))

        duration_spin(self.days_var, 0, 30, "DAYS")
        duration_spin(self.hours_var, 0, 23, "HRS")
        duration_spin(self.minutes_var, 0, 59, "MIN")
        self.duration_row = row

        self.duration_preview = tk.Label(card, text="", font=body_font(10), bg=SURFACE, fg=INK_DIM)
        self.duration_preview.pack(anchor="w", padx=16, pady=(10, 14))
        self._update_duration_ui()

    def _set_duration(self, d, h, m):
        self.days_var.set(d)
        self.hours_var.set(h)
        self.minutes_var.set(m)

    def _read_duration(self):
        """(days, hours, minutes), or None if a field is empty/not a number."""
        try:
            return self.days_var.get(), self.hours_var.get(), self.minutes_var.get()
        except tk.TclError:
            return None

    def _update_duration_ui(self):
        if self.duration_preview is None or not anim._alive(self.duration_preview):
            return
        dur = self._read_duration()
        for chip, value in self.chips:
            if dur == value:
                chip.set_colors(CYAN, ON_CYAN, CYAN_HOVER)
            else:
                chip.set_colors(SURFACE_2, INK_DIM, BORDER)
        if dur is None:
            self.duration_preview.config(text="Days, hours and minutes must be whole numbers.", fg=PINK)
            return
        d, h, m = dur
        if d == 0 and h == 0 and m == 0:
            self.duration_preview.config(text="Set a duration above zero.", fg=PINK)
            return
        end = datetime.now() + timedelta(days=d, hours=h, minutes=m)
        self.duration_preview.config(text=f"Unlocks {end.strftime('%A %d %b, %H:%M')}", fg=INK_DIM)

    def _build_intent_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "YOUR FOCUS FOR THIS SESSION (OPTIONAL)")
        tk.Entry(
            card, textvariable=self.intent_var, bg=SURFACE_2, fg=INK, insertbackground=INK,
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=CYAN, font=body_font(11),
        ).pack(fill="x", padx=16, pady=(0, 14), ipady=7)

    def _update_selection_summary(self):
        if self.selection_summary is None or not anim._alive(self.selection_summary):
            return
        n_apps = sum(v.get() for v in self.app_vars.values())
        n_sites = sum(v.get() for v in self.domain_vars.values())
        self.selection_summary.config(
            text=f"{n_apps} APP(S) · {n_sites} WEBSITE(S) SELECTED  ·  CHANGE THEM ON START"
        )

    def _on_start_block(self):
        dlg = SelectionDialog(self, self.app_vars, self.domain_vars)
        self.wait_window(dlg)
        if not dlg.result:
            return

        selected_apps = [k for k, v in self.app_vars.items() if v.get()]
        selected_domains = [k for k, v in self.domain_vars.items() if v.get()]

        dur = self._read_duration()
        if dur is None or dur == (0, 0, 0):
            self.toast("Set a duration above zero first (and check no field is empty).", "warn")
            if anim._alive(self.duration_row):
                anim.shake(self.duration_row, amplitude=14)
            return
        days, hours, minutes = dur
        offset = f"+{days} days +{hours} hours +{minutes} minutes"
        unlock_human = run_date("+%A, %Y-%m-%d %H:%M:%S %Z", offset=offset)
        unlock_calendar = run_date("+%Y-%m-%d %H:%M:%S", offset=offset)
        intent = self.intent_var.get().strip()

        duration_label = " ".join(
            f"{n}{u}" for n, u in ((days, "d"), (hours, "h"), (minutes, "m")) if n
        )
        app_names = [label for k, label in all_apps() if k in selected_apps]
        domain_names = [label for k, label in all_domains() if k in selected_domains]
        summary = [
            f"Duration: {duration_label}, until {unlock_human}",
            f"Apps: {', '.join(app_names) or '(none)'}",
            f"Websites: {', '.join(domain_names) or '(none)'}",
            "This cannot be undone early once engaged.",
        ]

        dlg = PasswordConfirmDialog(self, "Engage Lock", summary, "LOCK")
        self.wait_window(dlg)
        if dlg.result is None:
            return

        args = [
            unlock_human, unlock_calendar,
            ",".join(selected_apps) or "none",
            ",".join(selected_domains) or "none",
            intent,
            custom_defs_arg(set(selected_apps)),
            custom_sites_arg(set(selected_domains)),
        ]

        def done(overlay, proc):
            end_date = datetime.strptime(unlock_calendar.split()[0], "%Y-%m-%d").date()
            prev_stats = load_stats()
            new_stats = bump_streak(unlock_calendar)
            ends_at = datetime.strptime(unlock_calendar, "%Y-%m-%d %H:%M:%S").timestamp()
            record_session(date.today(), end_date, selected_apps, selected_domains, intent,
                           started_at=time.time(), ends_at=ends_at)
            self._seed_template_tasks(unlock_human)
            self._ensure_logger()
            check_milestones(prev_stats, new_stats)
            badges, new_ids, first_run = sync_badges(load_history(), load_stats(),
                                                     pomo_history=load_pomo_history())
            earned_now = [b for b in badges if b["id"] in new_ids]
            n = len(selected_apps) + len(selected_domains)
            overlay.celebrate(
                "LOCKED IN",
                [f"until {unlock_human}", f"{n} thing(s) blocked  ·  {new_stats['streak']}-day streak"],
                on_reveal=lambda: self._after_lock(earned_now, first_run),
                style=self._celebration_style(),
            )

        self._run_privileged("apply", args, dlg.result, "ENGAGING LOCK", done, "Nothing was locked.")

    def _run_privileged(self, action, args, password, busy_text, on_success, failure_note):
        """Run a privileged step (sudo on Linux, a UAC prompt on Windows; see
        focuslock_platform.run_privileged) on a worker thread behind a
        spinner overlay, so the window keeps animating instead of freezing.
        Tk is only touched from the main thread: the worker just stores the
        result, which the main loop polls for."""
        self._busy = True
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        overlay = Overlay(self)
        overlay.working(busy_text)
        result = {}

        def worker():
            try:
                result["proc"] = plat.run_privileged(action, args, password)
            except Exception as e:  # e.g. sudo missing; reported below
                result["error"] = e
        threading.Thread(target=worker, daemon=True).start()
        started = time.monotonic()

        def poll():
            # Keep the spinner up at least briefly so it reads as deliberate.
            if not result or time.monotonic() - started < 0.8:
                self.after(60, poll)
                return
            proc = result.get("proc")
            if proc is not None and proc.returncode == 0:
                on_success(overlay, proc)
                return
            message = self._failure_text(proc, result.get("error"), failure_note)
            overlay.leave(lambda: self._finish_busy(refresh=False))
            self.after(350, lambda: self.toast(message, "error", 7000))
        self.after(60, poll)

    @staticmethod
    def _failure_text(proc, error, note):
        if error is not None:
            what = "the lock step" if plat.IS_WINDOWS else "sudo"
            return f"Couldn't run {what}: {error}. {note}"
        stderr = (proc.stderr or "").strip()
        if stderr == plat.UAC_CANCELLED:
            return f"Administrator permission wasn't given. {note}"
        if "incorrect password" in stderr or "Sorry, try again" in stderr:
            return f"Wrong sudo password. {note}"
        tail = stderr[-400:] if stderr else "Unknown error."
        return f"{tail}\n{note}"

    def _after_lock(self, earned_now, first_run):
        self._finish_busy()
        if not earned_now:
            return
        if first_run:
            self._announce_first_badges(earned_now)
        else:
            self.after(900, lambda: self._show_badge_unlocks(earned_now))

    # ---------- apps ----------

    def _build_apps_view(self, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        c = self.scroller.inner
        custom = load_custom_apps()
        title = tk.Label(c, text="Apps & Websites", font=display_font(26, "bold"), bg=BG, fg=YELLOW)
        title.pack(pady=(26, 4))
        n_sites = len(load_custom_sites())
        subtitle = tk.Label(c, text=f"{len(APPS) + len(DOMAINS)} BUILT IN  \u00b7  {len(custom) + n_sites} ADDED BY YOU",
                            font=mono_font(10), bg=BG, fg=INK_FAINT)
        subtitle.pack(pady=(0, 18))
        content = tk.Frame(c, bg=BG)
        content.pack(fill="x", padx=44)

        if self._was_locked:
            tk.Label(content, text="A lock is running: apps you add now get blocked from your next lock, "
                                   "and removed ones stay blocked until this one ends.",
                     font=body_font(10), bg=BG, fg=YELLOW, wraplength=640, justify="left").pack(
                anchor="w", pady=(0, 8))

        self._build_recommendations_card(content, intro)

        card = card_frame(content)
        card.pack(fill="x", pady=8)
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="YOUR APPS", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        make_pill(head, "+ Add app", self._on_add_app, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(10, "bold"), width=130, height=36).pack(side="right")
        listing = tk.Frame(card, bg=SURFACE)
        listing.pack(fill="x", padx=16, pady=(0, 14))
        if not custom:
            tk.Label(listing, text="Nothing added yet. Use + Add app for any game or program not in the "
                                   "built-in list below.", font=body_font(10), bg=SURFACE, fg=INK_FAINT,
                     wraplength=600, justify="left").pack(anchor="w", pady=6)
        kinds = dict(CUSTOM_KINDS)
        for i, a in enumerate(custom):
            fill, _ = accent_colors(KIND_ACCENTS.get(a.get("kind"), "pink"))
            row = tk.Frame(listing, bg=SURFACE)
            row.pack(fill="x", pady=4)
            tk.Label(row, text="\u25cf", font=body_font(11), bg=SURFACE, fg=fill).pack(side="left")
            # Packed before the text so a long path can never squeeze it out.
            small_pill(row, "Remove", lambda key=a["key"]: self._on_remove_app(key), height=28).pack(side="right")
            text_col = tk.Frame(row, bg=SURFACE)
            text_col.pack(side="left", padx=(8, 0), fill="x", expand=True)
            top = tk.Frame(text_col, bg=SURFACE)
            top.pack(anchor="w")
            tk.Label(top, text=a["name"], font=body_font(11, "bold"), bg=SURFACE, fg=INK).pack(side="left")
            tk.Label(top, text=kinds.get(a.get("kind"), "Other").upper(), font=mono_font(8, "bold"),
                     bg=SURFACE, fg=fill).pack(side="left", padx=(10, 0))
            where = f"Flatpak \u00b7 {a['target']}" if a["source"] == "flatpak" else short_path(a["target"], 44)
            tk.Label(text_col, text=where, font=mono_font(9), bg=SURFACE, fg=INK_FAINT, anchor="w").pack(anchor="w")
            if intro:
                anim.fade_in(row, SURFACE, 350, delay_ms=400 + 60 * i)

        self._build_sites_card(content, intro)

        builtin = card_frame(content)
        builtin.pack(fill="x", pady=8)
        card_title(builtin, "BUILT IN")
        flow = FlowFrame(builtin, bg=SURFACE)
        flow.pack(fill="x", padx=14, pady=(0, 10))
        builtin_items = [(label, YELLOW if key in DEV_TOOLS else PINK) for key, label in APPS]
        builtin_items += [(label, CYAN) for _, label in DOMAINS]
        for i, (label, color) in enumerate(builtin_items):
            chip = Chip(flow, label, color)
            flow.add(chip)
            if intro:
                chip.pop(delay_ms=500 + i * 35)
        tk.Label(builtin, text="Pick what to block each time in Start Block. FocusLock never lets you add system "
                               "tools, your desktop's programs, or FocusLock itself \u2014 blocking those "
                               "could break your computer or stop a lock from lifting.",
                 font=body_font(9), bg=SURFACE, fg=INK_FAINT, wraplength=640, justify="left").pack(
            anchor="w", padx=16, pady=(0, 14))
        tk.Frame(content, bg=BG, height=40).pack()
        if intro:
            stagger_in([subtitle] + content.winfo_children(), step=80, duration=400, start=150)
        else:
            stagger_in([c], step=0, duration=300)

    # ---- recommendations (entertainment scan) ----

    def _build_recommendations_card(self, parent, intro):
        consent = load_settings().get("scan_consent")
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="RECOMMENDED FOR YOU", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        body = tk.Frame(card, bg=SURFACE)
        body.pack(fill="x", padx=16, pady=(0, 14))

        if consent is not True:
            tk.Label(body, text="FocusLock can look through the apps on this computer and suggest games, chat "
                                "and video apps to block. It only reads app lists here \u2014 nothing is "
                                "uploaded, and nothing is blocked until you press Add.",
                     font=body_font(10), bg=SURFACE, fg=INK_DIM, wraplength=620, justify="left").pack(anchor="w")
            make_pill(body, "Allow scanning", lambda: self._set_scan_consent(True), bg=PINK, fg=ON_PINK,
                      hover_bg=PINK_HOVER, font=mono_font(10, "bold"), width=170, height=38).pack(
                anchor="w", pady=(12, 0))
            return

        result = self.scan_result
        if result is None:
            label = tk.Label(body, text="", font=body_font(10), bg=SURFACE, fg=INK_DIM)
            label.pack(anchor="w")
            if self._scan_running:
                anim.loop(label, 1200, lambda ph: label.config(
                    text="Looking through your apps" + "." * (1 + int(ph * 3))))
            else:
                label.config(text="Not scanned yet.")
                small_pill(body, "Scan now", self._start_scan, height=30, fg=INK).pack(anchor="w", pady=(8, 0))
            return

        recs = result["recommendations"]
        small_pill(head, "Rescan", self._start_scan, height=28).pack(side="right")
        if recs:
            small_pill(head, f"Add all {len(recs)}", lambda: self._add_recommendations([r["id"] for r in recs]),
                       height=28, bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER).pack(side="right", padx=(0, 6))
        else:
            tk.Label(body, text="Nothing new \u2014 everything that looks like entertainment is already built "
                                "in or added.", font=body_font(10), bg=SURFACE, fg=INK_DIM).pack(anchor="w")
        for i, rec in enumerate(recs):
            fill, _ = accent_colors(SCAN_CATEGORY_ACCENTS[rec["category"]])
            row = tk.Frame(body, bg=SURFACE)
            row.pack(fill="x", pady=4)
            small_pill(row, "Add", lambda rid=rec["id"]: self._add_recommendations([rid]), height=28, width=64,
                       bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER).pack(side="right")
            small_pill(row, "Ignore", lambda rid=rec["id"]: self._ignore_recommendation(rid), height=28,
                       width=76).pack(side="right", padx=(0, 6))
            tk.Label(row, text="\u25cf", font=body_font(11), bg=SURFACE, fg=fill).pack(side="left")
            col = tk.Frame(row, bg=SURFACE)
            col.pack(side="left", padx=(8, 0), fill="x", expand=True)
            top = tk.Frame(col, bg=SURFACE)
            top.pack(anchor="w")
            tk.Label(top, text=rec["name"], font=body_font(11, "bold"), bg=SURFACE, fg=INK).pack(side="left")
            tk.Label(top, text=rec["category"].upper(), font=mono_font(8, "bold"), bg=SURFACE, fg=fill).pack(
                side="left", padx=(10, 0))
            where = f"Flatpak \u00b7 {rec['target']}" if rec["source"] == "flatpak" else short_path(rec["target"], 48)
            tk.Label(col, text=f"{rec['reason']}  \u00b7  {where}", font=body_font(9), bg=SURFACE,
                     fg=INK_FAINT).pack(anchor="w")
            if intro:
                anim.fade_in(row, SURFACE, 350, delay_ms=350 + 60 * i)
        steam = result.get("steam_games", [])
        if steam:
            shown = ", ".join(steam[:5]) + (f" and {len(steam) - 5} more" if len(steam) > 5 else "")
            tk.Label(body, text=f"Covered whenever Steam is blocked: {shown}.", font=body_font(9), bg=SURFACE,
                     fg=INK_FAINT, wraplength=620, justify="left").pack(anchor="w", pady=(8, 0))
        small_pill(body, "Turn off scanning", lambda: self._set_scan_consent(False), height=26).pack(
            anchor="w", pady=(10, 0))

    def _scan_on_startup(self):
        consent = load_settings().get("scan_consent")
        if consent is None:
            if self._busy:  # e.g. an unlock screen is showing; ask once it's gone
                self.after(1500, self._scan_on_startup)
                return
            dlg = ScanPermissionDialog(self)
            self.wait_window(dlg)
            self._set_scan_consent(dlg.result)
        elif consent:
            self._start_scan()

    def _set_scan_consent(self, allowed):
        settings = load_settings()
        settings["scan_consent"] = bool(allowed)
        save_settings(settings)
        if allowed:
            self._start_scan()
        else:
            self.scan_result = None
            if self.tab == "apps":
                self.refresh(intro=False)

    def _start_scan(self):
        """Scan on a worker thread (it only reads files); results land in
        self.scan_result and new finds get a toast."""
        if self._scan_running:
            return
        self._scan_running = True
        ignored = load_settings().get("scan_ignored", [])
        box = {}

        def worker():
            try:
                box["result"] = scanner.scan(ignored)
            except Exception as e:  # never let a scan problem take down the app
                box["error"] = e
        threading.Thread(target=worker, daemon=True).start()

        def poll():
            if not box:
                self.after(150, poll)
                return
            self._scan_running = False
            if "result" in box:
                self.scan_result = box["result"]
                self._announce_new_recommendations()
            if self.tab == "apps" and not self._busy:
                self.refresh(intro=False)
        self.after(150, poll)
        if self.tab == "apps" and not self._busy:
            self.refresh(intro=False)  # show the "looking..." state

    def _announce_new_recommendations(self):
        settings = load_settings()
        seen = set(settings.get("scan_seen", []))
        new = [r for r in self.scan_result["recommendations"] if r["id"] not in seen]
        if not new:
            return
        settings["scan_seen"] = sorted(seen | {r["id"] for r in new})
        save_settings(settings)
        names = ", ".join(r["name"] for r in new[:3]) + (" and more" if len(new) > 3 else "")
        if not self._busy:
            self.toast(f"Found {len(new)} app(s) that look like entertainment ({names}). "
                       "See Recommended in the APPS tab.", "info", 6000, sound="toggle_on")

    def _add_recommendations(self, rec_ids):
        recs = [r for r in (self.scan_result or {}).get("recommendations", []) if r["id"] in rec_ids]
        custom = load_custom_apps()
        keys = {a["key"] for a in custom} | {k for k, _ in all_apps()}
        core = core_package_paths([r["target"] for r in recs if r["source"] == "path"])
        added = []
        for rec in recs:
            problem = (check_flatpak_id(rec["target"]) if rec["source"] == "flatpak"
                       else check_custom_path(rec["target"], core_paths=core))
            if problem:
                continue  # it changed since the scan; the next rescan won't offer it
            name = sanitize_app_name(rec["name"]) or "App"
            key = make_custom_key(name, keys)
            keys.add(key)
            custom.append({"key": key, "name": name, "kind": rec["kind"], "source": rec["source"],
                           "target": rec["target"]})
            added.append(name)
        save_custom_apps(custom)
        self._sync_app_vars()
        self.scan_result["recommendations"] = [r for r in self.scan_result["recommendations"]
                                               if r["id"] not in rec_ids]
        if added:
            snd.play("toggle_on")
            self.toast(f"Added {', '.join(added)}. They're in Start Block's switches now.", "success", 4500)
        self.refresh(intro=False)

    def _ignore_recommendation(self, rec_id):
        settings = load_settings()
        settings["scan_ignored"] = sorted(set(settings.get("scan_ignored", [])) | {rec_id})
        save_settings(settings)
        self.scan_result["recommendations"] = [r for r in self.scan_result["recommendations"] if r["id"] != rec_id]
        self.refresh(intro=False)

    def _build_sites_card(self, parent, intro):
        sites = load_custom_sites()
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="YOUR WEBSITES", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        make_pill(head, "+ Add website", self._on_add_site, bg=CYAN, fg=ON_CYAN, hover_bg=CYAN_HOVER,
                  font=mono_font(10, "bold"), width=150, height=36).pack(side="right")
        listing = tk.Frame(card, bg=SURFACE)
        listing.pack(fill="x", padx=16, pady=(0, 14))
        if not sites:
            tk.Label(listing, text="Nothing added yet. Use + Add website for any site not in the built-in list.",
                     font=body_font(10), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", pady=6)
        for i, site in enumerate(sites):
            row = tk.Frame(listing, bg=SURFACE)
            row.pack(fill="x", pady=4)
            small_pill(row, "Remove", lambda key=site["key"]: self._on_remove_site(key), height=28).pack(side="right")
            tk.Label(row, text="\u25cf", font=body_font(11), bg=SURFACE, fg=CYAN).pack(side="left")
            col = tk.Frame(row, bg=SURFACE)
            col.pack(side="left", padx=(8, 0), fill="x", expand=True)
            tk.Label(col, text=site["name"], font=body_font(11, "bold"), bg=SURFACE, fg=INK).pack(anchor="w")
            shown = [d for d in site["domains"] if not d.startswith("www.")]
            tk.Label(col, text=", ".join(shown), font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w")
            if intro:
                anim.fade_in(row, SURFACE, 350, delay_ms=400 + 60 * i)

    def _on_add_site(self):
        sites = load_custom_sites()
        dlg = AddWebsiteDialog(self, sites)
        self.wait_window(dlg)
        if not dlg.result:
            return
        sites.append(dlg.result)
        save_custom_sites(sites)
        self._sync_domain_vars()
        snd.play("toggle_on")
        self.toast(f"Added {dlg.result['name']}. It's in Start Block's website switches now.", "success", 4000)
        self.refresh(intro=False)

    def _on_remove_site(self, key):
        sites = load_custom_sites()
        removed = [s for s in sites if s["key"] == key]
        save_custom_sites([s for s in sites if s["key"] != key])
        self._sync_domain_vars()
        if removed:
            self.toast(f"Removed {removed[0]['name']}.", "info", 3000)
        self.refresh(intro=False)

    def _sync_domain_vars(self):
        """Keep one switch variable per website as custom sites come and go."""
        keys = [k for k, _ in all_domains()]
        for k in list(self.domain_vars):
            if k not in keys:
                del self.domain_vars[k]
        for k in keys:
            if k not in self.domain_vars:
                var = tk.BooleanVar(value=True)
                var.trace_add("write", lambda *_: self._update_selection_summary())
                self.domain_vars[k] = var

    def _on_add_app(self):
        custom = load_custom_apps()
        dlg = AddAppDialog(self, custom)
        self.wait_window(dlg)
        if not dlg.result:
            return
        custom.append(dlg.result)
        save_custom_apps(custom)
        self._sync_app_vars()
        if self.scan_result:  # no need to keep recommending what was just added by hand
            self.scan_result["recommendations"] = [r for r in self.scan_result["recommendations"]
                                                   if r["target"] != dlg.result["target"]]
        snd.play("toggle_on")
        self.toast(f"Added {dlg.result['name']}. It's in Start Block's switches now.", "success", 4000)
        self.refresh(intro=False)

    def _on_remove_app(self, key):
        custom = load_custom_apps()
        removed = [a for a in custom if a["key"] == key]
        save_custom_apps([a for a in custom if a["key"] != key])
        self._sync_app_vars()
        if removed:
            self.toast(f"Removed {removed[0]['name']}.", "info", 3000)
        self.refresh(intro=False)

    def _sync_app_vars(self):
        """Keep one switch variable per app as custom apps come and go."""
        dev = dev_tool_keys()
        keys = [k for k, _ in all_apps()]
        for k in list(self.app_vars):
            if k not in keys:
                del self.app_vars[k]
        for k in keys:
            if k not in self.app_vars:
                var = tk.BooleanVar(value=k not in dev)
                var.trace_add("write", lambda *_: self._update_selection_summary())
                self.app_vars[k] = var

    # ---------- pomodoro ----------
    # A timer only: nothing here blocks, unblocks or closes anything.

    def _build_pomodoro_view(self, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        c = self.scroller.inner
        title = tk.Label(c, text="Pomodoro", font=display_font(26, "bold"), bg=BG, fg=YELLOW)
        title.pack(pady=(26, 4))
        subtitle = tk.Label(c, text="IN PROGRESS" if self.pomo else "BUILD YOUR SESSION",
                            font=mono_font(10), bg=BG, fg=INK_FAINT)
        subtitle.pack(pady=(0, 18))
        content = tk.Frame(c, bg=BG)
        content.pack(fill="x", padx=44)
        if self.pomo:
            self._build_pomo_running(content)
        else:
            self._build_pomo_editor(content)
        self._build_ambient_card(content)
        tk.Label(content, text="A TIMER ONLY — IT DOESN'T BLOCK ANYTHING. START A LOCK TOO IF YOU WANT APPS BLOCKED.",
                 font=mono_font(8), bg=BG, fg=INK_FAINT, wraplength=620).pack(pady=(18, 40))
        if intro:
            stagger_in([subtitle] + content.winfo_children(), step=80, duration=400, start=150)
        else:
            stagger_in([c], step=0, duration=300)

    # ---- editor ----

    def _build_pomo_editor(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "ADD A PHASE")
        row1 = tk.Frame(card, bg=SURFACE)
        row1.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(row1, text="NAME", font=mono_font(10), bg=SURFACE, fg=CYAN).pack(side="left", padx=(0, 8))
        tk.Entry(row1, textvariable=self.pomo_name_var, width=16, bg=SURFACE_2, fg=INK, insertbackground=INK,
                 relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=CYAN,
                 font=body_font(11)).pack(side="left", ipady=5, padx=(0, 12))
        self.pomo_kind_chips = []
        for name, accent in POMO_KINDS:
            chip = small_pill(row1, name, lambda n=name, a=accent: self._pomo_pick_kind(n, a), height=30)
            chip.pack(side="left", padx=(0, 6))
            self.pomo_kind_chips.append((chip, accent))
        self._pomo_style_kind_chips()

        row2 = tk.Frame(card, bg=SURFACE)
        row2.pack(fill="x", padx=16, pady=(0, 6))
        for var, hi, caption in ((self.pomo_h, 23, "HRS"), (self.pomo_m, 59, "MIN"), (self.pomo_s, 59, "SEC")):
            tk.Spinbox(row2, from_=0, to=hi, textvariable=var, width=3, bg=SURFACE_2, fg=INK,
                       buttonbackground=SURFACE_2, insertbackground=INK, relief="flat", highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=CYAN, font=body_font(12),
                       justify="center").pack(side="left", ipady=4)
            tk.Label(row2, text=caption, font=mono_font(10), bg=SURFACE, fg=CYAN).pack(side="left", padx=(6, 14))
        make_pill(row2, "+ Add phase", self._pomo_add, bg=CYAN, fg=ON_CYAN, hover_bg=CYAN_HOVER,
                  font=mono_font(10, "bold"), width=130, height=36).pack(side="right")
        self.pomo_time_row = row2
        self.pomo_add_error = tk.Label(card, text="", font=body_font(9), bg=SURFACE, fg=PINK)
        self.pomo_add_error.pack(anchor="w", padx=16, pady=(0, 10))

        card2 = card_frame(parent)
        card2.pack(fill="x", pady=8)
        card_title(card2, "YOUR PHASES")
        self.pomo_list_frame = tk.Frame(card2, bg=SURFACE)
        self.pomo_list_frame.pack(fill="x", padx=16, pady=(0, 8))
        rounds_row = tk.Frame(card2, bg=SURFACE)
        rounds_row.pack(fill="x", padx=16, pady=(4, 14))
        tk.Label(rounds_row, text="ROUNDS", font=mono_font(10), bg=SURFACE, fg=CYAN).pack(side="left", padx=(0, 8))
        tk.Spinbox(rounds_row, from_=1, to=20, textvariable=self.pomo_rounds_var, width=3, bg=SURFACE_2, fg=INK,
                   buttonbackground=SURFACE_2, insertbackground=INK, relief="flat", highlightthickness=1,
                   highlightbackground=BORDER, highlightcolor=CYAN, font=body_font(12),
                   justify="center").pack(side="left", ipady=4)
        self.pomo_total_label = tk.Label(rounds_row, text="", font=mono_font(9), bg=SURFACE, fg=INK_DIM)
        self.pomo_total_label.pack(side="left", padx=(14, 0))

        start_row = tk.Frame(parent, bg=BG)
        start_row.pack(pady=(14, 0))
        self.pomo_start_btn = make_pill(start_row, "Start Pomodoro", self._pomo_start, bg=PINK, fg=ON_PINK,
                                        hover_bg=PINK_HOVER, font=mono_font(13, "bold"), width=250, height=56)
        self.pomo_start_btn.pack()
        self._render_pomo_list()

    def _pomo_pick_kind(self, name, accent):
        self.pomo_name_var.set(name)
        self.pomo_accent = accent
        self._pomo_style_kind_chips()

    def _pomo_style_kind_chips(self):
        for chip, accent in self.pomo_kind_chips:
            fill, ink = accent_colors(accent)
            if accent == self.pomo_accent:
                chip.set_colors(fill, ink, anim.lighten(fill, 0.2))
            else:
                chip.set_colors(SURFACE_2, INK_DIM, BORDER)

    def _render_pomo_list(self, new_index=None):
        frame = getattr(self, "pomo_list_frame", None)
        if frame is None or not anim._alive(frame):
            return
        for w in frame.winfo_children():
            w.destroy()
        phases = self.pomo_plan["phases"]
        if not phases:
            tk.Label(frame, text="No phases yet. Add one above — e.g. Study 30:00, then Code 10:00.",
                     font=body_font(10), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", pady=6)
        for i, ph in enumerate(phases):
            fill, _ = accent_colors(ph.get("accent", "pink"))
            row = tk.Frame(frame, bg=SURFACE)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="●", font=body_font(11), bg=SURFACE, fg=fill).pack(side="left")
            tk.Label(row, text=f"{i + 1}.", font=mono_font(10), bg=SURFACE, fg=INK_FAINT, width=3).pack(side="left")
            tk.Label(row, text=ph["name"], font=body_font(11), bg=SURFACE, fg=INK).pack(side="left")
            tk.Label(row, text=format_hms(ph["seconds"]), font=mono_font(11, "bold"), bg=SURFACE,
                     fg=fill).pack(side="left", padx=(12, 0))
            small_pill(row, "Remove", lambda i=i: self._pomo_remove(i), height=26).pack(side="right", padx=(6, 0))
            if i < len(phases) - 1:
                small_pill(row, "Down", lambda i=i: self._pomo_move(i, 1), height=26).pack(side="right", padx=(6, 0))
            if i > 0:
                small_pill(row, "Up", lambda i=i: self._pomo_move(i, -1), height=26).pack(side="right", padx=(6, 0))
            if i == new_index:
                anim.fade_in(row, SURFACE, 400)
        self._pomo_update_total()

    def _pomo_rounds(self):
        try:
            return max(1, min(20, int(self.pomo_rounds_var.get())))
        except (tk.TclError, ValueError):
            return None

    def _pomo_update_total(self):
        label = getattr(self, "pomo_total_label", None)
        phases = self.pomo_plan["phases"]
        if label is not None and anim._alive(label):
            per_round = sum(p["seconds"] for p in phases)
            rounds = self._pomo_rounds()
            if not phases:
                label.config(text="")
            elif rounds is None:
                label.config(text="Rounds must be a whole number.", fg=PINK)
            else:
                label.config(text=f"{format_hms(per_round)} PER ROUND  ·  "
                                  f"{format_span(per_round * rounds, False).upper()} TOTAL", fg=INK_DIM)
        btn = getattr(self, "pomo_start_btn", None)
        if btn is not None and anim._alive(btn):
            btn.set_enabled(bool(phases) and self._pomo_rounds() is not None)

    def _pomo_rounds_changed(self):
        rounds = self._pomo_rounds()
        if rounds is not None:
            self.pomo_plan["rounds"] = rounds
            save_pomo_plan(self.pomo_plan)
        self._pomo_update_total()

    def _pomo_add(self):
        error = self.pomo_add_error
        try:
            secs = self.pomo_h.get() * 3600 + self.pomo_m.get() * 60 + self.pomo_s.get()
        except tk.TclError:
            secs = None
        if not secs or secs < 0:
            snd.play("error")
            error.config(text="Set a length above zero (hours, minutes or seconds)."
                         if secs is not None else "Hours, minutes and seconds must be whole numbers.")
            anim.shake(self.pomo_time_row, amplitude=12)
            return
        error.config(text="")
        phases = self.pomo_plan["phases"]
        name = self.pomo_name_var.get().strip()[:24] or f"Phase {len(phases) + 1}"
        phases.append({"name": name, "seconds": secs, "accent": self.pomo_accent})
        save_pomo_plan(self.pomo_plan)
        self._render_pomo_list(new_index=len(phases) - 1)

    def _pomo_move(self, i, delta):
        phases = self.pomo_plan["phases"]
        j = i + delta
        phases[i], phases[j] = phases[j], phases[i]
        save_pomo_plan(self.pomo_plan)
        self._render_pomo_list(new_index=j)

    def _pomo_remove(self, i):
        del self.pomo_plan["phases"][i]
        save_pomo_plan(self.pomo_plan)
        self._render_pomo_list()

    # ---- running ----

    def _pomo_start(self):
        phases = [dict(p) for p in self.pomo_plan["phases"]]
        rounds = self._pomo_rounds()
        if not phases or rounds is None:
            return
        self.pomo = {
            "phases": phases, "rounds": rounds, "round_idx": 0, "phase_idx": 0,
            "deadline": time.monotonic() + phases[0]["seconds"], "paused": False, "remaining": None,
            "started_at": time.time(), "seconds_done": 0, "rounds_done": 0, "focus_done": 0,
        }
        self._pomo_next_key = None
        self._pomo_schedule()
        self.refresh(intro=True)

    def _pomo_schedule(self):
        if self._pomo_after is not None:
            self.after_cancel(self._pomo_after)
        self._pomo_after = self.after(200, self._pomo_tick)

    def _pomo_remaining(self):
        st = self.pomo
        if not st:
            return 0
        return st["remaining"] if st["paused"] else st["deadline"] - time.monotonic()

    def _pomo_tick(self):
        self._pomo_after = None
        # A loop, so several phases ending during one stall (e.g. a frozen
        # desktop) are all accounted for rather than skipped.
        while self.pomo and not self.pomo["paused"] and self._pomo_remaining() <= 0:
            self._pomo_advance()
        st = self.pomo
        if not st:
            self.tabbar.set_tab_text("pomodoro")
            return
        phase = st["phases"][st["phase_idx"]]
        fill, _ = accent_colors(phase.get("accent", "pink"))
        if self.tab == "pomodoro":
            self.tabbar.set_tab_text("pomodoro")
            self._pomo_update_running()
        else:
            clock = "PAUSED" if st["paused"] else format_hms(math.ceil(self._pomo_remaining()))
            self.tabbar.set_tab_text("pomodoro", f"● {clock}", fill)
        self._pomo_schedule()

    def _pomo_advance(self):
        st = self.pomo
        phases = st["phases"]
        ended = phases[st["phase_idx"]]
        st["seconds_done"] += ended["seconds"]
        if not is_break_phase(ended):
            st["focus_done"] = st.get("focus_done", 0) + ended["seconds"]
        st["phase_idx"] += 1
        if st["phase_idx"] >= len(phases):
            st["phase_idx"] = 0
            st["round_idx"] += 1
            st["rounds_done"] += 1
            if st["round_idx"] >= st["rounds"]:
                self._pomo_finish(completed=True)
                return
        nxt = phases[st["phase_idx"]]
        st["deadline"] += nxt["seconds"]
        message = f"{ended['name']} done. Next: {nxt['name']} ({format_hms(nxt['seconds'])})."
        snd.play("chime")
        notify("FocusLock Pomodoro", message)
        if not self._busy:
            self.toast(message, "info", 5000)

    def _pomo_toggle_pause(self):
        st = self.pomo
        if not st:
            return
        if st["paused"]:
            st["deadline"] = time.monotonic() + st["remaining"]
            st["paused"] = False
        else:
            st["remaining"] = max(0.0, st["deadline"] - time.monotonic())
            st["paused"] = True
        btn = getattr(self, "pomo_pause_btn", None)
        if btn is not None and anim._alive(btn):
            btn.label = "Resume" if st["paused"] else "Pause"
            btn._draw()

    def _pomo_stop_early(self, note=None):
        """Ask for the typed sentence; stop the session if given. Returns
        True if the session was stopped."""
        if not self.pomo:
            return True
        dlg = StopEarlyDialog(self, note)
        self.wait_window(dlg)
        if not dlg.result or not self.pomo:
            return False
        self._pomo_finish(completed=False)
        return True

    def _pomo_finish(self, completed):
        st, self.pomo = self.pomo, None
        if self._pomo_after is not None:
            self.after_cancel(self._pomo_after)
            self._pomo_after = None
        seconds = st["seconds_done"]
        focus = st.get("focus_done", 0)
        if not completed:
            phase = st["phases"][st["phase_idx"]]
            current = phase["seconds"]
            remaining = st["remaining"] if st["paused"] else st["deadline"] - time.monotonic()
            partial = max(0, min(current, current - remaining))
            seconds += partial
            if not is_break_phase(phase):
                focus += partial
        record_pomo({
            "started_at": int(st["started_at"]), "ended_at": int(time.time()),
            "rounds_planned": st["rounds"], "rounds_done": st["rounds_done"],
            "seconds_done": int(seconds), "focus_seconds": int(focus), "completed": completed,
        })
        self.tabbar.set_tab_text("pomodoro")
        if completed:
            message = (f"Pomodoro finished — {st['rounds']} round(s), "
                       f"{format_span(seconds, False)} timed. Well done.")
            notify("FocusLock Pomodoro", message)
            self.toast(message, "success", 7000, sound="chime")
        else:
            self.toast("Pomodoro stopped early.", "warn", 4000)
        if self.tab == "pomodoro" and not self._busy:
            self.refresh(intro=True)
        if not self._busy:
            self._sync_badges()

    def _build_pomo_running(self, parent):
        st = self.pomo
        ring_row = tk.Frame(parent, bg=BG)
        ring_row.pack(pady=(0, 6))
        PomodoroRing(ring_row, self).pack()
        self.pomo_round_label = tk.Label(parent, text="", font=mono_font(11, "bold"), bg=BG, fg=INK)
        self.pomo_round_label.pack(pady=(0, 2))
        self.pomo_elapsed_label = tk.Label(parent, text="", font=mono_font(9), bg=BG, fg=INK_FAINT)
        self.pomo_elapsed_label.pack(pady=(0, 12))

        buttons = tk.Frame(parent, bg=BG)
        buttons.pack(pady=(0, 10))
        self.pomo_pause_btn = make_pill(buttons, "Resume" if st["paused"] else "Pause", self._pomo_toggle_pause,
                                        bg=CYAN, fg=ON_CYAN, hover_bg=CYAN_HOVER, font=mono_font(11, "bold"),
                                        width=150, height=44)
        self.pomo_pause_btn.pack(side="left", padx=6)
        small_pill(buttons, "Stop early", self._pomo_stop_early, width=150, height=44,
                   font=mono_font(11)).pack(side="left", padx=6)

        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "UP NEXT")
        self.pomo_next_frame = tk.Frame(card, bg=SURFACE)
        self.pomo_next_frame.pack(fill="x", padx=16, pady=(0, 14))
        self._pomo_next_key = None
        self._pomo_update_running()

    def _pomo_update_running(self):
        st = self.pomo
        label = getattr(self, "pomo_round_label", None)
        if not st or label is None or not anim._alive(label):
            return
        phases = st["phases"]
        label.config(text=f"ROUND {st['round_idx'] + 1} / {st['rounds']}  ·  "
                          f"PHASE {st['phase_idx'] + 1} / {len(phases)}")
        current = phases[st["phase_idx"]]["seconds"]
        done = st["seconds_done"] + max(0, current - self._pomo_remaining())
        total = sum(p["seconds"] for p in phases) * st["rounds"]
        self.pomo_elapsed_label.config(text=f"{format_hms(done)} OF {format_hms(total)} DONE")

        key = (st["round_idx"], st["phase_idx"])
        if key == self._pomo_next_key:
            return
        self._pomo_next_key = key
        frame = self.pomo_next_frame
        for w in frame.winfo_children():
            w.destroy()
        upcoming = []
        r, i = st["round_idx"], st["phase_idx"]
        while len(upcoming) < 5:
            i += 1
            if i >= len(phases):
                i, r = 0, r + 1
            if r >= st["rounds"]:
                break
            upcoming.append((r, phases[i]))
        if not upcoming:
            tk.Label(frame, text="This is the last phase — finish strong.", font=body_font(10),
                     bg=SURFACE, fg=INK_DIM).pack(anchor="w")
        for n, (rnd, ph) in enumerate(upcoming):
            fill, _ = accent_colors(ph.get("accent", "pink"))
            row = tk.Frame(frame, bg=SURFACE)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="●", font=body_font(11), bg=SURFACE, fg=fill).pack(side="left")
            tk.Label(row, text=ph["name"], font=body_font(11), bg=SURFACE, fg=INK if n == 0 else INK_DIM).pack(
                side="left", padx=(6, 0))
            tk.Label(row, text=format_hms(ph["seconds"]), font=mono_font(10, "bold"), bg=SURFACE,
                     fg=fill).pack(side="left", padx=(10, 0))
            tk.Label(row, text=f"ROUND {rnd + 1}", font=mono_font(8), bg=SURFACE, fg=INK_FAINT).pack(side="right")
            anim.fade_in(row, SURFACE, 300, delay_ms=60 * n)

    # ---------- focus sounds ----------

    def _build_ambient_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="FOCUS SOUNDS", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        Equalizer(head, lambda: self.ambient.state == "playing").pack(side="left", padx=(10, 0))
        status = tk.Label(head, text="", font=mono_font(9), bg=SURFACE, fg=INK_FAINT)
        status.pack(side="left", padx=(8, 0))

        row = FlowFrame(card, bg=SURFACE, gap=6)
        row.pack(fill="x", padx=16, pady=(0, 6))
        chips = []
        hours = self._focus_hours()
        for key, label in [(None, "Off")] + ambient.SOUNDS:
            lock = self._lock_label("sound", key, hours) if key else None
            chip = small_pill(row, f"{label} \u00b7 {lock}" if lock else label, lambda k=key: self._ambient_pick(k),
                              height=30, sound=None)
            chip.locked = bool(lock)
            row.add(chip)
            chips.append((chip, key))

        vol_row = tk.Frame(card, bg=SURFACE)
        vol_row.pack(fill="x", padx=16, pady=(4, 14))
        tk.Label(vol_row, text="VOLUME", font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack(side="left")
        Slider(vol_row, self.ambient.volume, self._ambient_volume, width=220).pack(side="left", padx=(8, 0))

        def refresh_state(_phase=None):
            playing = self.ambient.current
            for chip, key in chips:
                if chip.locked:
                    chip.set_colors(anim.blend(SURFACE, SURFACE_2, 0.5), INK_FAINT, SURFACE_2, redraw=False)
                elif key == playing and key is not None:
                    chip.set_colors(PINK, ON_PINK, PINK_HOVER, redraw=False)
                elif key is None and playing is None:
                    chip.set_colors(SURFACE_2, INK, BORDER, redraw=False)
                else:
                    chip.set_colors(SURFACE_2, INK_DIM, BORDER, redraw=False)
                chip._draw()
            if self.ambient.error:
                text = self.ambient.error
            elif self.ambient.state == "preparing":
                text = "preparing..."
            elif self.ambient.state == "playing":
                text = "playing \u2014 keeps going on every tab"
            else:
                text = ""
            if status.cget("text") != text:
                status.config(text=text)
        anim.loop(status, 500, refresh_state)
        refresh_state()

    def _ambient_pick(self, key):
        if key and self._refuse_locked("sound", key, dict(ambient.SOUNDS)[key]):
            return
        snd.play("click")
        if key is None:
            self.ambient.stop()
        else:
            self.ambient.play(key)
            self.ambient_last = key
        self._save_ambient()

    def _ambient_volume(self, value):
        self.ambient.set_volume(value)
        self._save_ambient()

    def _save_ambient(self):
        settings = load_settings()
        settings["ambient"] = {"sound": self.ambient_last, "volume": round(self.ambient.volume, 3)}
        save_settings(settings)

    # ---------- weekly recap ----------

    def _maybe_show_recap(self):
        """Once per week, on the first launch after it ends, show last week's
        recap -- if anything happened that week."""
        grab = self.grab_current()
        if self._busy or (grab is not None and grab is not self):
            self.after(2000, self._maybe_show_recap)  # wait for dialogs/overlays to finish
            return
        last_week = date.today() - timedelta(days=date.today().weekday() + 7)
        settings = load_settings()
        if settings.get("recap_week") == last_week.isoformat():
            return
        settings["recap_week"] = last_week.isoformat()
        save_settings(settings)
        data = week_recap(last_week, load_history(), load_pomo_history(), load_badges())
        if data["active"]:
            self._show_recap(data)

    def _show_recap(self, data=None, this_week=False):
        if self._busy:
            return
        if data is None:
            monday = date.today() - timedelta(days=date.today().weekday())
            week = monday if this_week else monday - timedelta(days=7)
            data = week_recap(week, load_history(), load_pomo_history(), load_badges())
            if not data["active"]:
                self.toast("Nothing recorded " + ("this week yet." if this_week else "last week."), "info")
                return
        self._busy = True
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        Overlay(self).recap(data, load_stats(), on_done=lambda: self._finish_busy(refresh=False))

    # ---------- badges ----------

    def _sync_badges(self, announce=True):
        """Recompute badges, record new ones, and celebrate them. Returns
        the full badge list."""
        badges, new_ids, first_run = sync_badges(load_history(), load_stats(),
                                                 pomo_history=load_pomo_history())
        earned_now = [b for b in badges if b["id"] in new_ids]
        if announce and earned_now:
            if first_run:
                self._announce_first_badges(earned_now)
            else:
                self.after(300, lambda: self._show_badge_unlocks(earned_now))
        return badges

    def _announce_first_badges(self, earned):
        # Badges earned retroactively from past history: one quiet notice
        # rather than a parade of unlock screens.
        names = ", ".join(b["name"] for b in earned)
        self.after(700, lambda: self.toast(
            f"You've already earned {len(earned)} badge(s) from past sessions: {names}. "
            "See the BADGES tab.", "success", 6000, sound="badge"))

    def _show_badge_unlocks(self, earned):
        grab = self.grab_current()
        if self._busy or (grab is not None and grab is not self):
            self.after(1000, lambda: self._show_badge_unlocks(earned))
            return
        self._busy = True
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        Overlay(self).badges(earned, on_done=lambda: self._finish_busy(refresh=self.tab == "badges"))

    def _build_badges_view(self, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        c = self.scroller.inner
        badges = self._sync_badges()
        earned = [b for b in badges if b["earned"]]
        locked = [b for b in badges if not b["earned"]]

        title = tk.Label(c, text="Badges", font=display_font(26, "bold"), bg=BG, fg=YELLOW)
        title.pack(pady=(26, 4))
        subtitle = tk.Label(c, text=f"{len(earned)} OF {len(badges)} EARNED", font=mono_font(10),
                            bg=BG, fg=INK_FAINT)
        subtitle.pack(pady=(0, 10))
        content = tk.Frame(c, bg=BG)
        content.pack(fill="x", padx=44)
        self._build_level_card(content, intro)
        self._build_challenges_card(content, intro)
        self._build_rewards_card(content, intro)
        bar_row = tk.Frame(content, bg=BG)
        bar_row.pack(fill="x", padx=120, pady=(0, 18))
        ProgressBar(bar_row, len(earned) / len(badges)).pack(fill="x")

        delay = 300
        for heading, group in (("EARNED", earned), ("STILL TO EARN", locked)):
            if not group:
                continue
            tk.Label(content, text=heading, font=mono_font(11, "bold"), bg=BG, fg=CYAN).pack(
                anchor="w", pady=(10, 6))
            grid = tk.Frame(content, bg=BG)
            grid.pack(fill="x")
            for col in range(3):
                grid.columnconfigure(col, weight=1, uniform="badge")
            for i, badge in enumerate(group):
                tile = self._badge_tile(grid, badge, delay if intro else None, intro)
                tile.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
                delay += 45
        tk.Frame(content, bg=BG, height=40).pack()
        if intro:
            stagger_in([subtitle] + content.winfo_children(), step=60, duration=380, start=100)
        else:
            stagger_in([c], step=0, duration=320)

    def _badge_tile(self, parent, badge, medal_delay, intro):
        tile = card_frame(parent)
        Medal(tile, badge, intro_delay=medal_delay).pack(pady=(14, 0))
        tk.Label(tile, text=badge["name"], font=body_font(11, "bold"), bg=SURFACE,
                 fg=INK if badge["earned"] else INK_DIM).pack()
        tk.Label(tile, text=badge["desc"], font=body_font(9), bg=SURFACE, fg=INK_FAINT,
                 wraplength=180, justify="center").pack(padx=10, pady=(2, 8))
        fill, _ = accent_colors(badge["accent"])
        if badge["earned"]:
            when = date.fromisoformat(badge["earned_on"]).strftime("%d %b %Y").upper()
            tk.Label(tile, text=f"EARNED {when}", font=mono_font(8, "bold"), bg=SURFACE, fg=fill).pack(
                pady=(0, 14))
        else:
            value, target = badge["value"], badge["target"]
            shown = f"{value:.1f}" if badge["unit"] == "h" and value < 10 else str(int(value))
            row = tk.Frame(tile, bg=SURFACE)
            row.pack(fill="x", padx=16, pady=(0, 14))
            tk.Label(row, text=f"{shown} / {target}{badge['unit']}", font=mono_font(8), bg=SURFACE,
                     fg=INK_FAINT).pack(side="right", padx=(8, 0))
            MiniBar(row, value / target, fill, intro=intro).pack(side="left", fill="x", expand=True)
        return tile

    # ---------- lock templates ----------

    def _all_templates(self):
        return [dict(t, builtin=True) for t in BUILTIN_TEMPLATES] + load_templates()

    def _build_templates_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        self.templates_card = card
        self._fill_templates_card()

    def _fill_templates_card(self):
        card = self.templates_card
        for w in card.winfo_children():
            w.destroy()
        card_title(card, "TEMPLATES")
        flow = FlowFrame(card, bg=SURFACE, gap=6)
        flow.pack(fill="x", padx=16, pady=(0, 8))
        for t in self._all_templates():
            on = t["id"] == self._template_id
            flow.add(small_pill(flow, t["name"], lambda t=t: self._apply_template(t), height=30,
                                bg=PINK if on else SURFACE_2, fg=ON_PINK if on else INK,
                                hover_bg=PINK_HOVER if on else BORDER))
            if not t.get("builtin"):
                flow.add(small_pill(flow, "\u00d7", lambda t=t: self._delete_template(t), height=30, width=30,
                                    fg=INK_FAINT))
        flow.add(small_pill(flow, "+ Save current\u2026", self._save_template, height=30, fg=CYAN))
        hint = "One click sets the duration, what to block, the focus sound and the session note."
        if self._template_tasks:
            n = len(self._template_tasks)
            hint = f"{n} starter task{'s' if n != 1 else ''} will be added to your list when the lock starts."
        tk.Label(card, text=hint, font=body_font(9), bg=SURFACE, fg=INK_FAINT, justify="left",
                 wraplength=560).pack(anchor="w", padx=16, pady=(0, 14))

    def _apply_template(self, t):
        snd.play("click")
        d, h, m = (int(x) for x in t["duration"])
        self._set_duration(d, h, m)
        apps, domains = template_selection(t, list(self.app_vars), dev_tool_keys(), list(self.domain_vars))
        for k, var in self.app_vars.items():
            if var.get() != (k in apps):
                var.set(k in apps)
        for k, var in self.domain_vars.items():
            if var.get() != (k in domains):
                var.set(k in domains)
        self.intent_var.set(t.get("intent", ""))
        sound = t.get("sound")
        if sound in dict(ambient.SOUNDS) and self.ambient.current != sound and not self._lock_label("sound", sound):
            self._ambient_pick(sound)
        self._template_id = t["id"]
        self._template_tasks = list(t.get("tasks", []))
        self._fill_templates_card()
        stagger_in(self.templates_card.winfo_children(), step=30, duration=200, from_color=SURFACE)
        parts = [" ".join(f"{n}{u}" for n, u in ((d, "d"), (h, "h"), (m, "m")) if n),
                 f"{len(apps)} apps & {len(domains)} sites"]
        if sound in dict(ambient.SOUNDS):
            parts.append(dict(ambient.SOUNDS)[sound].lower())
        self.toast(f"Loaded \u201c{t['name']}\u201d: {', '.join(parts)}. Press Start Block when you're ready.",
                   "info", 4500)

    def _save_template(self):
        templates = load_templates()
        if len(templates) >= TEMPLATE_MAX:
            self.toast(f"You have {TEMPLATE_MAX} templates -- delete one first.", "warn")
            return
        dur = self._read_duration()
        if dur is None or dur == (0, 0, 0):
            self.toast("Set a duration above zero first.", "warn")
            return
        apps = [k for k, v in self.app_vars.items() if v.get()]
        domains = [k for k, v in self.domain_vars.items() if v.get()]
        sound = self.ambient.current
        d, h, m = dur
        summary = [f"{' '.join(f'{n}{u}' for n, u in ((d, 'd'), (h, 'h'), (m, 'm')) if n)}  \u00b7  "
                   f"{len(apps)} apps  \u00b7  {len(domains)} websites  \u00b7  "
                   f"{dict(ambient.SOUNDS).get(sound, 'no focus sound')}"]
        if self.intent_var.get().strip():
            summary.append(f"Session note: {self.intent_var.get().strip()}")
        dlg = TemplateDialog(self, summary)
        self.wait_window(dlg)
        if not dlg.result:
            return
        name, tasks = dlg.result
        t = {"id": f"u_{int(time.time() * 1000)}", "name": name, "duration": [d, h, m], "apps": apps,
             "domains": domains, "sound": sound, "intent": self.intent_var.get().strip(), "tasks": tasks}
        templates.append(t)
        save_templates(templates)
        self._template_id = t["id"]
        self._template_tasks = list(tasks)
        snd.play("toggle_on")
        self.toast(f"Saved template \u201c{name}\u201d.", "success", 3000)
        self._fill_templates_card()

    def _delete_template(self, t):
        save_templates([x for x in load_templates() if x["id"] != t["id"]])
        if self._template_id == t["id"]:
            self._template_id, self._template_tasks = None, []
        snd.play("toggle_off")
        self.toast(f"Deleted template \u201c{t['name']}\u201d.", "info", 3000)
        self._fill_templates_card()

    def _seed_template_tasks(self, unlock_human):
        """Put the loaded template's starter tasks on the new lock's list."""
        if not self._template_tasks:
            return
        progress = lock_progress()
        session = str(int(progress[0])) if progress else unlock_human
        data = session_tasks(session)
        have = {t["text"] for t in data["tasks"]}
        now = time.time()
        for i, text in enumerate(self._template_tasks):
            if text not in have and len(data["tasks"]) < TASK_MAX:
                data["tasks"].append({"id": f"{now + i / 1000:.6f}", "text": text, "done": False,
                                      "added_at": int(now)})
        save_tasks(data)
        self._template_tasks = []
        self._template_id = None

    # ---------- session task list ----------

    def _build_tasks_card(self, parent, session):
        self._task_session = session
        data = session_tasks(session)
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(head, text="TASKS FOR THIS SESSION", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(
            side="left")
        self.task_count = tk.Label(head, text="", font=mono_font(9, "bold"), bg=SURFACE, fg=INK_FAINT)
        self.task_count.pack(side="right")
        self.task_bar = ProgressBar(card, 0.0)
        self.task_bar.pack(fill="x", padx=16, pady=(0, 8))
        self.task_list = tk.Frame(card, bg=SURFACE)
        self.task_list.pack(fill="x", padx=16)
        self.task_rows = {}
        self.task_empty = tk.Label(self.task_list, text="Nothing here yet -- add what you want to get done "
                                                        "while you're locked in.",
                                   font=body_font(10), bg=SURFACE, fg=INK_FAINT, justify="left", wraplength=560)
        for task in data["tasks"]:
            self._add_task_row(task)

        add = tk.Frame(card, bg=SURFACE)
        add.pack(fill="x", padx=16, pady=(10, 4))
        self.task_entry = dialog_entry(add)
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.task_entry.bind("<Return>", lambda e: self._task_add())
        small_pill(add, "+ Add", self._task_add, height=34, fg=INK).pack(side="left", padx=(8, 0))
        tk.Label(card, text="Type a task and press Enter  \u00b7  click a box to tick it off", font=mono_font(8),
                 bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(2, 14))
        self._task_refresh_summary(animate=False)

    def _add_task_row(self, task, fade=False):
        tid = task.setdefault("id", f"{time.time():.6f}")
        row = TaskRow(self.task_list, task, lambda: self._task_toggle(tid), lambda: self._task_remove(tid))
        row.pack(fill="x")
        self.task_rows[tid] = row
        if fade:
            anim.fade_in(row, SURFACE, 300)
        return row

    def _task_data(self):
        """The saved list for the running lock (re-read, so it can't go stale)."""
        return session_tasks(self._task_session)

    def _task_refresh_summary(self, animate=True):
        done, total = task_counts(self._task_data()["tasks"])
        if total:
            self.task_empty.pack_forget()
            self.task_count.config(text=f"{done} / {total} DONE", fg=YELLOW if done == total else INK_FAINT)
        else:
            self.task_empty.pack(anchor="w", pady=(2, 4))
            self.task_count.config(text="")
        fraction = done / total if total else 0.0
        if animate:
            self.task_bar.set_fraction(fraction, duration=450)
        else:
            self.task_bar.set_fraction(fraction, duration=900, delay=500)

    def _task_add(self):
        entry = self.task_entry
        text = " ".join(entry.get().split())[:TASK_TEXT_MAX]
        if not text:
            snd.play("error")
            anim.shake(entry)
            return
        data = self._task_data()
        if len(data["tasks"]) >= TASK_MAX:
            self.toast(f"That's {TASK_MAX} tasks already -- tick some off first.", "warn")
            return
        task = {"id": f"{time.time():.6f}", "text": text, "done": False, "added_at": int(time.time())}
        data["tasks"].append(task)
        save_tasks(data)
        entry.delete(0, "end")
        snd.play("click")
        self._add_task_row(dict(task), fade=True)
        self._task_refresh_summary()

    def _task_toggle(self, tid):
        data = self._task_data()
        task = next((t for t in data["tasks"] if t.get("id") == tid), None)
        row = self.task_rows.get(tid)
        if task is None or row is None:
            return
        task["done"] = not task.get("done", False)
        task["done_at"] = int(time.time()) if task["done"] else None
        save_tasks(data)
        row.set_done(task["done"])
        done, total = task_counts(data["tasks"])
        if task["done"] and done == total:
            self.toast(f"Every task checked off ({total}/{total}) -- great session.", "success", 4500, sound="badge")
        else:
            snd.play("toggle_on" if task["done"] else "toggle_off")
        self._task_refresh_summary()
        if task["done"]:
            self.after(600, self._check_challenges)
            self.after(900, self._check_level)   # +5 XP might be the one that levels you up

    def _task_remove(self, tid):
        data = self._task_data()
        data["tasks"] = [t for t in data["tasks"] if t.get("id") != tid]
        save_tasks(data)
        row = self.task_rows.pop(tid, None)
        if row is not None and anim._alive(row):
            anim.fade_to(row, SURFACE, 160, on_done=row.destroy)
        snd.play("toggle_off")
        self._task_refresh_summary()

    # ---------- levels & XP ----------

    def _xp(self):
        return compute_xp(load_history(), load_pomo_history(), load_goals()["met"], load_tasks(),
                          load_badges() or {}, load_attempts(),
                          clean_since=load_settings().get("distraction_log_since"))

    def _level(self):
        return self._xp()["level"]

    def _build_level_strip(self, parent):
        """A compact LV + XP bar under the LOCK title; click for the details."""
        xp = self._xp()
        strip = tk.Frame(parent, bg=BG, cursor="hand2")
        strip.pack(pady=(0, 20))
        lv = tk.Label(strip, text=f"LV {xp['level']}", font=mono_font(10, "bold"), bg=BG, fg=YELLOW, cursor="hand2")
        lv.pack(side="left")
        bar = MiniBar(strip, (xp["total"] - xp["level_start"]) / (xp["level_end"] - xp["level_start"]), YELLOW)
        bar.configure(width=120)
        bar.pack(side="left", padx=8)
        name = tk.Label(strip, text=xp["title"].upper(), font=mono_font(9), bg=BG, fg=INK_FAINT, cursor="hand2")
        name.pack(side="left")
        ch = self._challenges()
        done = sum(c["done"] for c in ch)
        chal = tk.Label(strip, text=f"  \u00b7  CHALLENGES {done} / {len(ch)}", font=mono_font(9), bg=BG,
                        fg=YELLOW if done == len(ch) else CYAN, cursor="hand2")
        chal.pack(side="left")
        for w in (strip, lv, bar, name, chal):
            w.bind("<ButtonRelease-1>", lambda e: self.select_tab("badges"))

    def _build_level_card(self, parent, intro):
        xp = self._xp()
        card = card_frame(parent)
        card.pack(fill="x", pady=(0, 14))
        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=(16, 8))
        badge = tk.Canvas(row, width=92, height=92, bg=SURFACE, highlightthickness=0, bd=0)
        badge.pack(side="left")
        badge.create_oval(6, 6, 86, 86, fill=SURFACE_2, outline=YELLOW, width=4)
        badge.create_text(46, 42, text=str(xp["level"]), fill=YELLOW, font=display_font(28, "bold"))
        badge.create_text(46, 68, text="LEVEL", fill=INK_FAINT, font=mono_font(8, "bold"))
        info = tk.Frame(row, bg=SURFACE)
        info.pack(side="left", fill="x", expand=True, padx=(16, 0))
        tk.Label(info, text=xp["title"], font=display_font(20, "bold"), bg=SURFACE, fg=INK).pack(anchor="w")
        span = xp["level_end"] - xp["level_start"]
        into = xp["total"] - xp["level_start"]
        ProgressBar(info, into / span).pack(fill="x", pady=(6, 4))
        tk.Label(info, text=f"{into:,} / {span:,} XP to level {xp['level'] + 1}  \u00b7  {xp['total']:,} XP in all",
                 font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w")
        upcoming = []
        if xp["next_title"]:
            upcoming.append(f"Next title: {xp['next_title']} at level {xp['level'] + 1}")
        later = sorted((lvl, k) for k, lvl in THEME_UNLOCKS.items() if lvl > xp["level"])
        if later:
            lvl, key = later[0]
            upcoming.append(f"Next reward: the {dict(THEME_NAMES)[key]} theme at level {lvl}")
        for line in upcoming:
            tk.Label(info, text=line, font=body_font(10), bg=SURFACE, fg=CYAN).pack(anchor="w", pady=(2, 0))

        tk.Label(card, text="WHERE YOUR XP CAME FROM", font=mono_font(9, "bold"), bg=SURFACE, fg=INK_FAINT).pack(
            anchor="w", padx=16, pady=(10, 2))
        rows = [(label, value, YELLOW) for label, value in xp["parts"] if value]
        if rows:
            HBarList(card, rows, intro=intro).pack(fill="x", padx=16, pady=(0, 4))
        else:
            tk.Label(card, text="Nothing yet -- every focused minute is 1 XP. Start a lock to begin.",
                     font=body_font(10), bg=SURFACE, fg=INK_DIM).pack(anchor="w", padx=16)
        tk.Label(card, text=("1 XP per focused minute (up to 8 h a day)  \u00b7  +20 per lock (3 a day)  \u00b7  +50 per goal day  "
                             "\u00b7  +5 per task  \u00b7  +100 per badge  \u00b7  +25 per Pomodoro  \u00b7  "
                             "+30 per lock with no distractions  \u00b7  +100\u2013150 per weekly challenge"),
                 font=mono_font(8), bg=SURFACE, fg=INK_FAINT, justify="left", wraplength=600).pack(
            anchor="w", padx=16, pady=(4, 14))

    def _check_level(self):
        """Celebrate reaching a new level (once). The first time, just
        remember the current level -- no flood of level-ups for past work."""
        xp = self._xp()
        settings = load_settings()
        seen = settings.get("level_seen")
        if not isinstance(seen, int) or xp["level"] < seen:
            # First run -- or the level went down (XP rules changed, or an
            # older backup was restored): remember it quietly, so the next
            # real level-up still gets celebrated.
            settings["level_seen"] = xp["level"]
            save_settings(settings)
            return
        if xp["level"] == seen:
            return
        grab = self.grab_current()
        if self._busy or (grab is not None and grab is not self):
            self.after(3000, self._check_level)   # after dialogs / other celebrations
            return
        rewards = [f"Unlocked: the {dict(THEME_NAMES)[k]} theme (Settings)"
                   for k, lvl in sorted(THEME_UNLOCKS.items(), key=lambda kv: kv[1]) if seen < lvl <= xp["level"]]
        settings["level_seen"] = xp["level"]
        save_settings(settings)
        self._busy = True
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        Overlay(self).level_up(xp["level"], xp["title"], rewards,
                               on_done=lambda: self._finish_busy(refresh=self.tab in ("badges", "lock", "settings")))

    # ---------- total focus hours ----------

    def _build_total_hours_card(self, parent, intro):
        history, pomo = load_history(), load_pomo_history()
        by_day = focus_by_day(history, pomo)
        total = sum(by_day.values())
        if total <= 0:
            return
        locked = sum(focus_by_day(history, []).values())
        rewards = sum(min(v, 8 * 3600) for v in by_day.values())
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "TOTAL FOCUS HOURS")
        top = tk.Frame(card, bg=SURFACE)
        top.pack(fill="x", padx=16)
        number = tk.Label(top, text=f"{total / 3600:,.1f} h", font=display_font(34, "bold"), bg=SURFACE, fg=YELLOW)
        number.pack(side="left")
        if intro:
            count_up(number, total / 3600, lambda v: f"{v:,.1f} h", duration=1300, delay=300)
        split = tk.Frame(top, bg=SURFACE)
        split.pack(side="left", padx=(18, 0), fill="x", expand=True)
        tk.Label(split, text=f"Locks {format_hours(locked)}  \u00b7  Pomodoro {format_hours(total - locked)}",
                 font=mono_font(10, "bold"), bg=SURFACE, fg=INK).pack(anchor="w")
        tk.Label(split, text=f"{rewards / 3600:,.1f} h count toward Focus rewards (up to 8 h a day)",
                 font=body_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", pady=(2, 0))
        today = date.today()
        month0 = today.replace(day=1)
        week0 = today - timedelta(days=today.weekday())
        periods = [("TODAY", lambda d: d == today), ("THIS WEEK", lambda d: d >= week0),
                   ("THIS MONTH", lambda d: d >= month0), ("LAST 30 DAYS", lambda d: (today - d).days < 30)]
        grid = tk.Frame(card, bg=SURFACE)
        grid.pack(fill="x", padx=16, pady=(12, 14))
        for i, (caption, keep) in enumerate(periods):
            grid.columnconfigure(i, weight=1, uniform="period")
            secs = sum(v for d, v in by_day.items() if d <= today and keep(d))
            cell = tk.Frame(grid, bg=SURFACE)
            cell.grid(row=0, column=i, sticky="ew")
            tk.Label(cell, text=format_hours(secs), font=display_font(16, "bold"), bg=SURFACE,
                     fg=(PINK, CYAN, YELLOW, PINK)[i]).pack()
            tk.Label(cell, text=caption, font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack()

    # ---------- CSV export ----------

    def _build_export_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "EXPORT")
        tk.Label(card, text="Save your stats as a spreadsheet (CSV) -- opens in LibreOffice, Excel or Google Sheets.",
                 font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 10))
        row = tk.Frame(card, bg=SURFACE)
        row.pack(anchor="w", padx=16, pady=(0, 16))
        make_pill(row, "Daily summary\u2026", lambda: self._export("days"), bg=PINK, fg=ON_PINK, hover_bg=PINK_HOVER,
                  font=mono_font(9, "bold"), width=170, height=34).pack(side="left")
        small_pill(row, "Every session\u2026", lambda: self._export("sessions"), height=34).pack(side="left", padx=(8, 0))

    def _export(self, kind):
        name = f"focuslock-{'daily' if kind == 'days' else 'sessions'}-{date.today().isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            parent=self, title="Export FocusLock stats", defaultextension=".csv", initialfile=name,
            initialdir=os.path.expanduser("~"), filetypes=[("CSV spreadsheet", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            if kind == "days":
                n = export_daily_csv(path, load_history(), load_pomo_history(), load_goals()["met"], load_tasks(),
                                     load_attempts())
                what = f"{n} day{'s' if n != 1 else ''}"
            else:
                n = export_sessions_csv(path, load_history(), load_pomo_history(), dict(all_apps()),
                                        dict(all_domains()))
                what = f"{n} session{'s' if n != 1 else ''}"
        except OSError as e:
            self.toast(f"Couldn't export: {e.strerror or e}", "error")
            return
        self.toast(f"Exported {what} to {short_path(path)}.", "success", 4500, sound="chime")

    # ---------- stats calendar ----------

    def _build_calendar_card(self, parent, intro):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        self.calendar_card = card
        self._cal_month = date.today().replace(day=1)
        self._cal_day = date.today()
        self._fill_calendar_card(intro)

    def _fill_calendar_card(self, intro=False):
        card = self.calendar_card
        for w in card.winfo_children():
            w.destroy()
        month = self._cal_month
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="CALENDAR", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        nxt = small_pill(head, "\u203a", lambda: self._cal_shift(1), height=26, width=32)
        nxt.pack(side="right")
        if month >= date.today().replace(day=1):
            nxt.set_enabled(False)
        tk.Label(head, text=month.strftime("%B %Y").upper(), font=mono_font(10, "bold"), bg=SURFACE, fg=INK).pack(
            side="right", padx=10)
        small_pill(head, "\u2039", lambda: self._cal_shift(-1), height=26, width=32).pack(side="right")
        by_day = focus_by_day(load_history(), load_pomo_history())
        MonthCalendar(card, month, by_day, set(load_goals()["met"]), self._cal_day, self._cal_pick,
                      intro=intro).pack(fill="x", padx=12)
        legend = tk.Frame(card, bg=SURFACE)
        legend.pack(anchor="w", padx=16, pady=(2, 8))
        for text, color in (("more focus = brighter", PINK), ("goal met", YELLOW), ("today", CYAN)):
            tk.Label(legend, text="\u25cf", font=body_font(9), bg=SURFACE, fg=color).pack(side="left")
            tk.Label(legend, text=text, font=body_font(9), bg=SURFACE, fg=INK_FAINT).pack(side="left", padx=(3, 12))
        self.cal_details = tk.Frame(card, bg=SURFACE)
        self.cal_details.pack(fill="x", padx=16, pady=(0, 14))
        self._fill_day_details()

    def _cal_shift(self, delta):
        m = self._cal_month
        y, mo = divmod(m.year * 12 + m.month - 1 + delta, 12)
        new = date(y, mo + 1, 1)
        if new > date.today().replace(day=1):
            return
        self._cal_month = new
        self._cal_day = None
        self._fill_calendar_card()
        stagger_in(self.calendar_card.winfo_children(), step=30, duration=220, from_color=SURFACE)

    def _cal_pick(self, day):
        snd.play("click")
        self._cal_day = day
        self._fill_day_details()
        stagger_in(self.cal_details.winfo_children(), step=30, duration=220, from_color=SURFACE)

    def _fill_day_details(self):
        box = self.cal_details
        for w in box.winfo_children():
            w.destroy()
        day = self._cal_day
        if day is None:
            tk.Label(box, text="Click a day to see what happened.", font=body_font(10), bg=SURFACE,
                     fg=INK_FAINT).pack(anchor="w")
            return
        d = day_details(day, load_history(), load_pomo_history(), load_goals()["met"], load_tasks(), load_attempts())
        title = "TODAY" if day == date.today() else fmt_date(day, "%A %-d %B").upper()
        top = tk.Frame(box, bg=SURFACE)
        top.pack(fill="x", pady=(4, 6))
        tk.Label(top, text=title, font=mono_font(10, "bold"), bg=SURFACE, fg=YELLOW).pack(side="left")
        summary = f"{format_minutes(d['focus'] // 60)} focused"
        if d["goal"]:
            summary += f"  \u00b7  goal met ({format_minutes(d['goal'])})"
        tk.Label(top, text=summary, font=mono_font(9), bg=SURFACE, fg=INK_DIM).pack(side="right")
        lines = []
        for lk in d["locks"]:
            if lk["start"]:
                span = (f"{datetime.fromtimestamp(lk['start']):%H:%M}\u2013"
                        f"{'now' if lk['running'] else datetime.fromtimestamp(lk['end']).strftime('%H:%M')}")
                if date.fromtimestamp(lk["start"]) != day or date.fromtimestamp(lk["end"]) != day:
                    span = fmt_date(datetime.fromtimestamp(lk['start']), "%-d %b %H:%M") + " \u2192 " + (
                        "now" if lk["running"] else fmt_date(datetime.fromtimestamp(lk['end']), "%-d %b %H:%M"))
            else:
                span = "lock (no times recorded)"
            note = f" \u2014 {lk['intent']}" if lk["intent"] else ""
            lines.append(("LOCK", f"{span}  \u00b7  {lk['blocked']} blocked{note}", PINK))
        for p in d["pomos"]:
            state = "finished" if p["completed"] else "stopped early"
            lines.append(("POMODORO", f"{datetime.fromtimestamp(p['start']):%H:%M}  \u00b7  "
                                      f"{format_minutes(p['focus'] // 60)} focus  \u00b7  {state}", CYAN))
        for text in d["tasks"]:
            lines.append(("TASK", f"\u2713 {text}", YELLOW))
        if d["attempts"]:
            lines.append(("REACHED FOR", ",  ".join(f"{self._app_name(k)} \u00d7{n}" for k, n in d["attempts"]), PINK))
        if not lines:
            tk.Label(box, text="Nothing recorded this day.", font=body_font(10), bg=SURFACE, fg=INK_FAINT).pack(anchor="w")
            return
        grid = tk.Frame(box, bg=SURFACE)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        for i, (kind, text, color) in enumerate(lines[:30]):
            tk.Label(grid, text=kind, font=mono_font(8, "bold"), bg=SURFACE, fg=color).grid(
                row=i, column=0, sticky="nw", padx=(0, 12), pady=2)
            tk.Label(grid, text=text, font=body_font(10), bg=SURFACE, fg=INK, anchor="w", justify="left",
                     wraplength=480).grid(row=i, column=1, sticky="w", pady=2)

    # ---------- focus rewards ----------

    def _focus_hours(self):
        return focus_hours(load_history(), load_pomo_history())

    def _lock_label(self, kind, key, hours=None, level=None):
        """"LV 6" / "50 H" while an item is still locked, else None."""
        if kind == "theme" and key in THEME_UNLOCKS:
            need = THEME_UNLOCKS[key]
            return f"LV {need}" if (self._level() if level is None else level) < need else None
        reward = reward_for(kind, key)
        if reward is None:
            return None
        return f"{reward[0]} H" if (self._focus_hours() if hours is None else hours) < reward[0] else None

    def _refuse_locked(self, kind, key, name):
        lock = self._lock_label(kind, key)
        if not lock:
            return False
        snd.play("error")
        if lock.startswith("LV"):
            self.toast(f"{name} unlocks at level {lock[3:]}. Keep focusing!", "info", 3500)
        else:
            self.toast(f"{name} unlocks after {lock[:-2]} focus hours \u2014 you're at {self._focus_hours():.1f}.",
                       "info", 4000)
        return True

    def _build_rewards_card(self, parent, intro):
        hours = self._focus_hours()
        card = card_frame(parent)
        card.pack(fill="x", pady=(0, 14))
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(head, text="FOCUS REWARDS", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        tk.Label(head, text=f"{hours:.1f} H FOCUSED", font=mono_font(9, "bold"), bg=SURFACE, fg=YELLOW).pack(side="right")
        nxt = next((rw for rw in REWARDS if hours < rw[0]), None)
        if nxt:
            prev = max([rw[0] for rw in REWARDS if rw[0] <= hours] + [0])
            ProgressBar(card, (hours - prev) / (nxt[0] - prev)).pack(fill="x", padx=16, pady=(0, 4))
            tk.Label(card, text=f"{nxt[0] - hours:.1f} h to go: {nxt[3]} ({nxt[1]})", font=mono_font(9), bg=SURFACE,
                     fg=INK_FAINT).pack(anchor="w", padx=16, pady=(0, 10))
        else:
            tk.Label(card, text="Every reward unlocked. Legendary.", font=mono_font(9, "bold"), bg=SURFACE,
                     fg=YELLOW).pack(anchor="w", padx=16, pady=(0, 10))
        grid = tk.Frame(card, bg=SURFACE)
        grid.pack(fill="x", padx=12, pady=(0, 6))
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="reward")
        kinds = {"sound": ("FOCUS SOUND", CYAN), "font": ("FONT", YELLOW), "theme": ("THEME", PINK),
                 "celebration": ("CELEBRATION", YELLOW)}
        for i, (hrs, kind, _key, name, desc) in enumerate(REWARDS):
            got = hours >= hrs
            tile = tk.Frame(grid, bg=SURFACE_2 if got else SURFACE, highlightthickness=1,
                            highlightbackground=BORDER if got else anim.blend(SURFACE, BORDER, 0.5))
            tile.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            bg = tile["bg"]
            tag, color = kinds[kind]
            top = tk.Frame(tile, bg=bg)
            top.pack(fill="x", padx=10, pady=(8, 0))
            tk.Label(top, text=tag, font=mono_font(8, "bold"), bg=bg, fg=color if got else INK_FAINT).pack(side="left")
            tk.Label(top, text="\u2713" if got else f"{hrs} H", font=mono_font(9, "bold"), bg=bg,
                     fg=YELLOW if got else INK_FAINT).pack(side="right")
            tk.Label(tile, text=name, font=body_font(11, "bold"), bg=bg, fg=INK if got else INK_DIM).pack(
                anchor="w", padx=10)
            tk.Label(tile, text=desc, font=body_font(9), bg=bg, fg=INK_DIM if got else INK_FAINT, justify="left",
                     wraplength=170).pack(anchor="w", padx=10, pady=(0, 8))
        tk.Label(card, text="Focus hours count every focused minute -- up to 8 h a day.", font=body_font(9),
                 bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(4, 14))

    def _check_rewards(self):
        """Celebrate rewards newly unlocked by focus hours. The very first time,
        it shows everything already earned (a nice reveal)."""
        hours = self._focus_hours()
        got = unlocked_rewards(hours)
        settings = load_settings()
        seen = settings.get("rewards_seen")
        new = [rw for rw in got if f"{rw[1]}:{rw[2]}" not in (seen or [])]
        if not new:
            if not isinstance(seen, list):
                settings["rewards_seen"] = []
                save_settings(settings)
            return
        grab = self.grab_current()
        if self._busy or (grab is not None and grab is not self):
            self.after(3000, self._check_rewards)
            return
        settings["rewards_seen"] = [f"{rw[1]}:{rw[2]}" for rw in got]
        save_settings(settings)
        self._busy = True
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        Overlay(self).rewards(new, hours, on_done=lambda: self._finish_busy(
            refresh=self.tab in ("badges", "settings", "lock")))

    # ---------- weekly challenges ----------

    def _challenges(self, week=None):
        return challenge_progress(week or week_start_of(date.today()), load_history(), load_pomo_history(),
                                  load_goals()["met"], load_tasks(), load_attempts(),
                                  clean_since=load_settings().get("distraction_log_since"))

    def _build_challenges_card(self, parent, intro):
        ch = self._challenges()
        card = card_frame(parent)
        card.pack(fill="x", pady=(0, 14))
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="THIS WEEK'S CHALLENGES", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")
        left = 7 - date.today().weekday()
        tk.Label(head, text=f"NEW ONES IN {left} DAY{'S' if left != 1 else ''}", font=mono_font(9), bg=SURFACE,
                 fg=INK_FAINT).pack(side="right")
        for c in ch:
            row = tk.Frame(card, bg=SURFACE)
            row.pack(fill="x", padx=16, pady=(0, 10))
            mark = TaskCheck(row, c["done"], lambda: None)
            mark.configure(cursor="")
            mark.pack(side="left", padx=(0, 10))
            text = tk.Frame(row, bg=SURFACE)
            text.pack(side="left", fill="x", expand=True)
            top = tk.Frame(text, bg=SURFACE)
            top.pack(fill="x")
            tk.Label(top, text=c["text"], font=body_font(11), bg=SURFACE,
                     fg=INK_FAINT if c["done"] else INK).pack(side="left")
            value = c["value"]
            shown = f"{value:g}" if isinstance(value, float) else str(value)
            tk.Label(top, text=f"{shown} / {c['target']}   +{c['xp']} XP", font=mono_font(9, "bold"), bg=SURFACE,
                     fg=YELLOW if c["done"] else INK_DIM).pack(side="right")
            MiniBar(text, min(1.0, value / c["target"]), YELLOW if c["done"] else PINK, intro=intro).pack(
                fill="x", pady=(4, 0))
        tk.Label(card, text="Finished challenges add their XP to your level.", font=body_font(9), bg=SURFACE,
                 fg=INK_FAINT).pack(anchor="w", padx=16, pady=(0, 14))

    def _check_challenges(self):
        """Announce each challenge the first time it's finished. The first
        run just remembers what's already done."""
        week = week_start_of(date.today())
        settings = load_settings()
        seen = settings.get("challenges_done")
        first = not isinstance(seen, list)
        seen = [] if first else seen
        new = [c for c in self._challenges(week) if c["done"] and f"{week.isoformat()}:{c['id']}" not in seen]
        if first or new:
            settings["challenges_done"] = (seen + [f"{week.isoformat()}:{c['id']}" for c in new])[-60:]
            save_settings(settings)
        if first or not new:
            return
        c = new[0]
        more = f" (+{len(new) - 1} more)" if len(new) > 1 else ""
        self.toast(f"Challenge complete: {c['text']}  +{c['xp']} XP{more}", "success", 6000, sound="badge")

    # ---------- distraction log ----------

    def _attempts_mtime(self):
        try:
            return os.stat(attempts_path()).st_mtime_ns
        except OSError:
            return None

    def _app_name(self, key):
        """Display name for a distraction-log key (an app or a website)."""
        names = dict(all_apps())
        names.update(all_domains())
        return names.get(key, "Something you've since removed")

    def _build_distraction_card(self, parent):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        self.distraction_card = card
        self._fill_distraction_card()

    def _fill_distraction_card(self):
        card = self.distraction_card
        for w in card.winfo_children():
            w.destroy()
        self._attempts_seen = self._attempts_mtime()
        since = self._lock_started or 0
        summ = attempt_summary(load_attempts(), since=since)
        card_title(card, "DISTRACTION LOG")
        if not summ["total"]:
            tk.Label(card, text="You haven't tried to open a blocked app or site this lock. Keep it up.", font=body_font(10),
                     bg=SURFACE, fg=INK_DIM).pack(anchor="w", padx=16, pady=(0, 14))
            return
        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(row, text=str(summ["total"]), font=display_font(26, "bold"), bg=SURFACE, fg=PINK).pack(side="left")
        times = "time" if summ["total"] == 1 else "times"
        tk.Label(row, text=f"{times} you reached for a blocked app or site this lock", font=body_font(10), bg=SURFACE,
                 fg=INK_DIM).pack(side="left", padx=(10, 0), pady=(8, 0))
        flow = FlowFrame(card, bg=SURFACE)
        flow.pack(fill="x", padx=14, pady=(0, 6))
        for key, n in summ["per_app"][:8]:
            flow.add(Chip(flow, f"{self._app_name(key)}  \u00d7{n}", PINK))
        ts, key = summ["last"]
        ago = max(0, int(time.time() - ts))
        ago_text = "just now" if ago < 60 else f"{format_minutes(ago // 60)} ago"
        tk.Label(card, text=f"Last: {self._app_name(key)} at {datetime.fromtimestamp(ts):%H:%M} ({ago_text})",
                 font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(0, 14))

    def _update_distractions(self):
        """Refresh the lock's distraction card when the log file changes."""
        card = getattr(self, "distraction_card", None)
        if card is None or not anim._alive(card):
            return
        if self._attempts_mtime() != self._attempts_seen:
            self._fill_distraction_card()
            stagger_in(card.winfo_children(), step=40, duration=260, from_color=SURFACE)

    def _build_distraction_stats_card(self, parent, intro):
        attempts = load_attempts()
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "DISTRACTIONS")
        if not attempts:
            tk.Label(card, text=("No attempts recorded yet. Each time you start a blocked app during a lock it's "
                                 "counted here -- and blocked websites too, from locks started with website "
                                 "logging (see Settings)."),
                     font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left", wraplength=560).pack(
                anchor="w", padx=16, pady=(0, 14))
            return
        now = time.time()
        today0 = datetime.combine(date.today(), datetime.min.time()).timestamp()
        week0 = today0 - date.today().weekday() * 86400
        cells = [("TODAY", attempt_summary(attempts, today0, now)["total"], PINK),
                 ("THIS WEEK", attempt_summary(attempts, week0, now)["total"], YELLOW),
                 ("ALL TIME", len(attempts), CYAN)]
        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=(0, 10))
        for caption, value, color in cells:
            cell = tk.Frame(row, bg=SURFACE)
            cell.pack(side="left", expand=True, fill="x")
            tk.Label(cell, text=str(value), font=display_font(22, "bold"), bg=SURFACE, fg=color).pack()
            tk.Label(cell, text=caption, font=mono_font(9), bg=SURFACE, fg=INK_FAINT).pack()
        summ = attempt_summary(attempts, 0, now)
        tk.Label(card, text="MOST REACHED FOR", font=mono_font(9, "bold"), bg=SURFACE, fg=INK_FAINT).pack(
            anchor="w", padx=16, pady=(4, 2))
        rows = [(self._app_name(k), n, PINK) for k, n in summ["per_app"][:5]]
        HBarList(card, rows, intro=intro).pack(fill="x", padx=16, pady=(0, 6))
        peak_hour = summ["per_hour"].index(max(summ["per_hour"]))
        tk.Label(card, text=f"WHEN  \u00b7  mostly around {hour_label(peak_hour)}", font=mono_font(9, "bold"),
                 bg=SURFACE, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(6, 2))
        HourChart(card, summ["per_hour"], intro=intro).pack(fill="x", padx=16, pady=(0, 14))

    # ---------- daily focus goal ----------

    def _pomo_live_focus(self):
        """Focus seconds of the running Pomodoro so far (breaks excluded)."""
        st = self.pomo
        if not st:
            return 0
        done = st.get("focus_done", 0)
        phase = st["phases"][st["phase_idx"]]
        if not is_break_phase(phase):
            done += max(0, min(phase["seconds"], phase["seconds"] - self._pomo_remaining()))
        return done

    def _today_focus(self):
        return focus_seconds_on(date.today(), load_history(), load_pomo_history(),
                                live_pomo_focus=self._pomo_live_focus())

    def _build_goal_card(self, parent, intro):
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        self.goal_card = card
        self._goal_editing = False
        self._fill_goal_card(intro)

    def _fill_goal_card(self, intro=False):
        card = self.goal_card
        for w in card.winfo_children():
            w.destroy()
        self.goal_ring = self.goal_amount = self.goal_status = None
        goals = load_goals()
        minutes = goals["minutes"]
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="TODAY", font=mono_font(10, "bold"), bg=SURFACE, fg=CYAN).pack(side="left")

        if minutes and not self._goal_editing:
            small_pill(head, "Change goal", lambda: self._edit_goal(True), height=26).pack(side="right")
            focus = self._today_focus()
            row = tk.Frame(card, bg=SURFACE)
            row.pack(fill="x", padx=16, pady=(0, 14))
            self.goal_ring = GoalRing(row, focus / (minutes * 60), intro=intro)
            self.goal_ring.pack(side="left")
            info = tk.Frame(row, bg=SURFACE)
            info.pack(side="left", padx=(16, 0), fill="x", expand=True)
            self.goal_amount = tk.Label(info, text=format_minutes(focus // 60), font=display_font(22, "bold"),
                                        bg=SURFACE, fg=INK)
            self.goal_amount.pack(anchor="w")
            tk.Label(info, text=f"focused, of your {format_minutes(minutes)} daily goal", font=body_font(10),
                     bg=SURFACE, fg=INK_DIM).pack(anchor="w")
            self.goal_status = tk.Label(info, text="", font=mono_font(9, "bold"), bg=SURFACE, fg=PINK)
            self.goal_status.pack(anchor="w", pady=(6, 0))
            streak = goal_streak(goals["met"])
            best = goal_best_streak(goals["met"])
            if streak or best:
                tk.Label(info, text=f"{streak}-day goal streak  \u00b7  best {best}", font=mono_font(9),
                         bg=SURFACE, fg=INK_FAINT).pack(anchor="w", pady=(2, 0))
            self._goal_status_text(focus, minutes)
            return

        if self._goal_editing:
            small_pill(head, "Cancel", lambda: self._edit_goal(False), height=26).pack(side="right")
        tk.Label(card, text=("Pick how long you want to focus each day. Locked time and Pomodoro focus phases "
                             "(not breaks) count toward it."),
                 font=body_font(10), bg=SURFACE, fg=INK_DIM, justify="left", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 10))
        chips = FlowFrame(card, bg=SURFACE, gap=6)
        chips.pack(fill="x", padx=16, pady=(0, 14))
        for m in GOAL_CHOICES:
            selected = m == minutes
            chip = small_pill(chips, format_minutes(m), lambda m=m: self._set_goal(m), height=30,
                              bg=PINK if selected else SURFACE_2, fg=ON_PINK if selected else INK,
                              hover_bg=PINK_HOVER if selected else BORDER)
            chips.add(chip)
        if minutes:
            chips.add(small_pill(chips, "No goal", lambda: self._set_goal(0), height=30))
        if not intro:
            stagger_in(card.winfo_children(), step=40, duration=260, from_color=SURFACE)

    def _goal_status_text(self, focus, minutes):
        if self.goal_status is None or not anim._alive(self.goal_status):
            return
        left = minutes * 60 - focus
        if left <= 0:
            self.goal_status.config(text="GOAL REACHED \u2014 NICE WORK", fg=YELLOW)
        else:
            self.goal_status.config(text=f"{format_minutes(math.ceil(left / 60)).upper()} TO GO", fg=PINK)

    def _edit_goal(self, editing):
        self._goal_editing = editing
        self._fill_goal_card()

    def _set_goal(self, minutes):
        goals = load_goals()
        goals["minutes"] = int(minutes)
        save_goals(goals)
        self._goal_editing = False
        snd.play("toggle_on" if minutes else "toggle_off")
        if minutes:
            self.toast(f"Daily goal set: {format_minutes(minutes)} of focus.", "info", 3000)
        self._fill_goal_card(intro=True)
        self._update_goal()

    def _update_goal(self):
        """Refresh the TODAY card and notice when the goal is reached
        (on any tab -- locks and Pomodoros count while you're elsewhere)."""
        goals = load_goals()
        minutes = goals["minutes"]
        if not minutes:
            return
        focus = self._today_focus()
        ring = getattr(self, "goal_ring", None)
        if ring is not None and anim._alive(ring):
            ring.set_fraction(focus / (minutes * 60))
            self.goal_amount.config(text=format_minutes(focus // 60))
            self._goal_status_text(focus, minutes)
        today = date.today()
        if focus >= minutes * 60 and record_goal_met(today, minutes):
            streak = goal_streak(load_goals()["met"])
            extra = f" That's a {streak}-day goal streak." if streak > 1 else ""
            self.toast(f"Daily goal reached \u2014 {format_minutes(focus // 60)} focused today!{extra}", "success",
                       6500, sound="badge")
            self.after(2500, self._check_challenges)
            self.after(3000, self._check_level)
            if ring is not None and anim._alive(ring):
                anim.confetti(ring, GoalRing.SIZE / 2, GoalRing.SIZE / 2, [PINK, CYAN, YELLOW],
                              fade_to=SURFACE, count=40)
                self.after(1900, lambda: self.goal_card is not None and anim._alive(self.goal_card)
                           and self._fill_goal_card())   # show the new streak

    def _build_goal_stats_card(self, parent, intro):
        goals = load_goals()
        minutes = goals["minutes"]
        card = card_frame(parent)
        card.pack(fill="x", pady=8)
        card_title(card, "DAILY GOAL")
        if not minutes and not goals["met"]:
            tk.Label(card, text="No daily goal yet. Set one on the LOCK tab to track it here.", font=body_font(10),
                     bg=SURFACE, fg=INK_DIM).pack(anchor="w", padx=16, pady=(0, 14))
            return
        today = date.today()
        days = [today - timedelta(days=13 - i) for i in range(14)]
        history, pomo = load_history(), load_pomo_history()
        live = self._pomo_live_focus()
        seconds = [focus_seconds_on(d, history, pomo, live_pomo_focus=live if d == today else 0) for d in days]
        met = goals["met"]
        n_met = sum(1 for d in days if d.isoformat() in met)
        summary = (f"Met {n_met} of the last 14 days  \u00b7  streak {goal_streak(met)}  \u00b7  "
                   f"best {goal_best_streak(met)}")
        if minutes:
            summary += f"  \u00b7  goal {format_minutes(minutes)}"
        hover = tk.Label(card, text=summary, font=mono_font(9), bg=SURFACE, fg=INK_FAINT)

        def on_hover(text):
            if anim._alive(hover):
                hover.config(text=text or summary, fg=INK if text else INK_FAINT)
        GoalHistory(card, days, seconds, (minutes or 60) * 60, met, on_hover=on_hover, intro=intro).pack(
            fill="x", padx=16)
        hover.pack(anchor="w", padx=16, pady=(4, 14))

    # ---------- keyboard shortcuts ----------

    def shortcut_sections(self):
        first, last = TABS[0][1], TABS[-1][1]
        return [
            ("NAVIGATE", [(["Ctrl", f"1–{len(TABS)}"], f"Jump to a tab ({first} … {last})"),
                          (["Ctrl", "Tab"], "Next tab"),
                          (["Wheel"], "Scroll the page")]),
            ("LOOK & SOUND", [(["Ctrl", "T"], "Next theme"),
                              (["Ctrl", "M"], "Sound effects on / off")]),
            ("IN DIALOGS", [(["Enter"], "Confirm / continue"),
                            (["Esc"], "Cancel / close")]),
            ("WHILE LOCKED", [(["Enter"], "Add the task you typed to this session's list")]),
            ("HELP", [(["?", "|F1"], "Show this list")]),
        ]

    def _on_help_key(self, event):
        # Typing a question mark into a text field shouldn't pop up help.
        if isinstance(self.focus_get(), (tk.Entry, tk.Text, tk.Spinbox)):
            return None
        self.show_shortcuts()
        return "break"

    def show_shortcuts(self):
        overlay = getattr(self, "_shortcuts_overlay", None)
        if overlay is not None and anim._alive(overlay):
            overlay.leave(self._close_shortcuts)   # pressing ? again closes it
            return
        if self._busy:
            return
        self._busy = True
        if self._toast is not None and anim._alive(self._toast):
            self._toast.destroy()
        overlay = self._shortcuts_overlay = Overlay(self)
        overlay.shortcuts(self.shortcut_sections(), on_done=self._close_shortcuts)
        self._shortcuts_esc = self.bind("<Escape>", lambda e: overlay.leave(self._close_shortcuts))

    def _close_shortcuts(self):
        try:
            self.unbind("<Escape>", self._shortcuts_esc)
        except (tk.TclError, AttributeError):
            pass
        self._shortcuts_overlay = None
        self._finish_busy(refresh=False)

    def _finish_busy(self, refresh=True):
        self._busy = False
        if refresh:
            self.refresh(intro=True)

    # ---------- locked view ----------

    def _build_locked_view(self, unlock_at, intro):
        self.scroller = ScrollableFrame(self.body, bg=BG)
        self.scroller.pack(fill="both", expand=True)
        f = self.scroller.inner

        badge = LockBadge(f, intro=intro)
        badge.pack(pady=(14, 0))
        title = tk.Label(f, text="FOCUSLOCK ACTIVE", font=display_font(22, "bold"), bg=BG, fg=PINK)
        title.pack(pady=(4, 2))
        tk.Label(f, text=f"Unlocks {unlock_at}", font=body_font(11), bg=BG, fg=INK_DIM).pack(pady=(0, 18))

        content = tk.Frame(f, bg=BG)
        content.pack(fill="x", padx=44)

        # ---- countdown + progress ----
        timer = card_frame(content)
        timer.pack(fill="x", pady=8)
        card_title(timer, "TIME LEFT")
        self.countdown_label = tk.Label(timer, text="", font=display_font(30, "bold"), bg=SURFACE, fg=CYAN)
        self.countdown_label.pack(pady=(0, 10))

        progress = lock_progress()
        if progress:
            self._lock_started, self._unlock_epoch = progress
        else:
            self._lock_started = None
            self._unlock_epoch = parse_unlock_time(unlock_at)
        self.progress_bar = None
        self.progress_label = None
        if self._lock_started is not None and self._unlock_epoch:
            self.progress_bar = ProgressBar(timer, self._progress_fraction())
            self.progress_bar.pack(fill="x", padx=16, pady=(0, 6))
            self.progress_label = tk.Label(timer, text="", font=mono_font(9), bg=SURFACE, fg=INK_FAINT)
            self.progress_label.pack(anchor="w", padx=16, pady=(0, 14))
        else:
            tk.Frame(timer, bg=SURFACE, height=6).pack()
        self._last_countdown = None
        self._update_countdown(pulse=False)

        self._build_goal_card(content, intro)

        # ---- intent ----
        intent = read_file(INTENT_FILE)
        if intent:
            intent_box = card_frame(content)
            intent_box.pack(fill="x", pady=8)
            card_title(intent_box, "YOUR FOCUS")
            tk.Label(
                intent_box, text=intent, font=body_font(13), bg=SURFACE, fg=INK,
                wraplength=640, justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 14))

        self._build_distraction_card(content)

        # ---- blocked items ----
        apps = detect_blocked_apps()
        domains = detect_blocked_domains()
        app_label_map = dict(all_apps())
        dev = dev_tool_keys()
        domain_label_map = dict(all_domains())
        box = card_frame(content)
        box.pack(fill="x", pady=8)
        card_title(box, f"CURRENTLY BLOCKED  ·  {len(apps) + len(domains)}")
        flow = FlowFrame(box, bg=SURFACE)
        flow.pack(fill="x", padx=14, pady=(0, 14))
        chips = [Chip(flow, app_label_map.get(k, k), YELLOW if k in dev else PINK) for k in apps]
        chips += [Chip(flow, domain_label_map.get(k, k), CYAN) for k in domains]
        if not chips:
            chips = [Chip(flow, "(nothing)", BORDER)]
        for i, chip in enumerate(chips):
            flow.add(chip)
            if intro:
                chip.pop(delay_ms=700 + i * 55)
        legend = tk.Frame(box, bg=SURFACE)
        legend.pack(anchor="w", padx=16, pady=(0, 12))
        for text, color in (("app", PINK), ("dev tool", YELLOW), ("website", CYAN)):
            tk.Label(legend, text="●", font=body_font(9), bg=SURFACE, fg=color).pack(side="left")
            tk.Label(legend, text=text, font=body_font(9), bg=SURFACE, fg=INK_FAINT).pack(side="left", padx=(3, 12))

        self._build_ambient_card(content)

        # ---- rotating tip ----
        first_tip = int(time.time() // 15) % len(FOCUS_TIPS)
        tip = tk.Label(content, text=FOCUS_TIPS[first_tip], font=body_font(10, "italic"),
                       bg=BG, fg=INK_DIM, wraplength=600)
        tip.pack(pady=(14, 4))
        self.after(15000, lambda: self._rotate_tip(tip, (first_tip + 1) % len(FOCUS_TIPS)))

        # ---- YouTube break ----
        if "youtube" in domains:
            today = datetime.now().strftime("%Y-%m-%d")
            if read_file(LAST_USED_FILE) == today:
                until = read_file(UNTIL_FILE)
                msg = "TODAY'S YOUTUBE BREAK ALREADY USED"
                if until:
                    msg += f" (RE-BLOCKED AT {until.upper()})"
                msg += ". RESETS AT MIDNIGHT."
                tk.Label(content, text=msg, font=mono_font(9), bg=BG, fg=INK_FAINT, wraplength=560).pack(pady=14)
            else:
                make_pill(
                    content, "Use today's YouTube break (1 hour)", self._on_youtube_break,
                    bg=CYAN, fg=ON_CYAN, hover_bg=CYAN_HOVER, font=mono_font(10, "bold"),
                    width=320, height=46,
                ).pack(pady=14)

        session = str(int(self._lock_started)) if self._lock_started else unlock_at
        self._build_tasks_card(content, session)

        tk.Label(
            content, text="NO EARLY UNLOCK, BY DESIGN — ONLY THE TIMER LIFTS THIS",
            font=mono_font(8), bg=BG, fg=INK_FAINT,
        ).pack(pady=(16, 40))

        if intro:
            anim.typewriter(title, "FOCUSLOCK ACTIVE", ms_per_char=45, delay_ms=500, blinks=0)
            stagger_in(f.winfo_children()[2:-1] + content.winfo_children(), step=80, duration=420, start=250)
        else:
            stagger_in([f], step=0, duration=320)

    def _rotate_tip(self, label, index):
        if not anim._alive(label):
            return
        label.config(text=FOCUS_TIPS[index])
        anim.fade_in(label, BG, 700)
        self.after(15000, lambda: self._rotate_tip(label, (index + 1) % len(FOCUS_TIPS)))

    def _progress_fraction(self):
        total = self._unlock_epoch - self._lock_started
        return (time.time() - self._lock_started) / total if total > 0 else 1.0

    def _update_countdown(self, pulse):
        label = self.countdown_label
        if label is None or not anim._alive(label) or not self._unlock_epoch:
            return
        secs = self._unlock_epoch - int(time.time())
        if secs <= 0:
            label.config(text="UNLOCKING...")
            return
        text = format_span(secs)
        label.config(text=text)
        if pulse and text != self._last_countdown:
            anim.pulse(label, "fg", anim.lighten(CYAN, 0.55), CYAN, 600)
        self._last_countdown = text
        if self.progress_bar is not None and anim._alive(self.progress_bar):
            frac = self._progress_fraction()
            if pulse:
                self.progress_bar.set_fraction(frac, duration=900)
            self.progress_label.config(
                text=f"{frac * 100:.1f}% DONE  ·  {format_span(time.time() - self._lock_started, False)} FOCUSED SO FAR"
            )

    def _on_youtube_break(self):
        dlg = PasswordConfirmDialog(
            self, "Use YouTube Break",
            [
                "Unblocks YouTube for exactly 1 hour, then re-blocks itself",
                "automatically. Usable once per day. No extensions.",
            ],
            "YOUTUBE1H",
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return

        reblock_human = run_date("+%A, %Y-%m-%d %H:%M:%S %Z", offset="+1 hour")
        reblock_calendar = run_date("+%Y-%m-%d %H:%M:%S", offset="+1 hour")

        def done(overlay, _proc):
            overlay.leave(self._finish_busy)
            self.after(450, lambda: self.toast(
                f"YouTube is unblocked until {reblock_human}. Use it well.", "info", 6000))

        self._run_privileged("youtube", [reblock_human, reblock_calendar], dlg.result,
                             "UNBLOCKING YOUTUBE", done, "YouTube is still blocked.")


if __name__ == "__main__":
    if not (plat.IS_LINUX or plat.IS_WINDOWS):
        print("FocusLock runs on Linux and Windows only.", file=sys.stderr)
        sys.exit(1)
    app = FocusLockApp()
    if os.environ.get("FOCUSLOCK_SMOKE_TEST"):
        # CI: open, draw for a few seconds, then exit cleanly (a crash in a
        # windowed build shows an error box and never exits, so this is how
        # the build check tells "started fine" apart from "crashed").
        app.after(int(os.environ["FOCUSLOCK_SMOKE_TEST"]) * 1000, app.destroy)
    app.mainloop()
