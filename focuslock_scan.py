"""Find installed apps that look like entertainment, so the Apps tab can
suggest blocking them. Read-only: it only reads app menu entries, folder
listings and Steam's library manifests on this computer, and never
changes, uploads or blocks anything by itself -- every suggestion still
needs the user to press Add.

Runs on a worker thread, so nothing here touches Tk.
"""
import os
import re
import shlex
import shutil
import subprocess

import focuslock_platform as plat
from focuslock_core import (
    BUILTIN_NAMES as LINUX_BUILTIN_NAMES, HIDDEN_FLATPAKS, WIN_APP_EXES, check_custom_path, check_flatpak_id, core_package_paths,
    load_custom_apps, win_exe_names,
)

HOME = os.path.expanduser("~")
DESKTOP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.join(HOME, ".local/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
    os.path.join(HOME, ".local/share/flatpak/exports/share/applications"),
    "/var/lib/snapd/desktop/applications",
]
STEAM_DIRS = [
    os.path.join(HOME, ".local/share/Steam/steamapps"),
    os.path.join(HOME, ".steam/steam/steamapps"),
    os.path.join(HOME, "snap/steam/common/.local/share/Steam/steamapps"),
]
if plat.IS_WINDOWS:
    STEAM_DIRS = [os.path.join(os.environ.get(v) or "", "Steam", "steamapps")
                  for v in ("ProgramFiles(x86)", "ProgramFiles") if os.environ.get(v)]
    START_MENU_DIRS = [os.path.join(os.environ.get(v) or "", "Microsoft", "Windows", "Start Menu", "Programs")
                       for v in ("ProgramData", "APPDATA") if os.environ.get(v)]
# Program names the built-in app list already covers.
BUILTIN_NAMES = (set().union(*(win_exe_names(v) for v in WIN_APP_EXES.values())) if plat.IS_WINDOWS
                 else LINUX_BUILTIN_NAMES)

GAME, CHAT, MEDIA = "Game", "Chat", "Video & music"
CATEGORY_KIND = {GAME: "game", CHAT: "other", MEDIA: "other"}

# Well-known distractions that don't always tag themselves in their menu
# entry. Matched against the entry's file name, program name and title.
KNOWN = {
    GAME: ["lutris", "heroic", "itch", "prismlauncher", "multimc", "polymc", "atlauncher",
           "retroarch", "dolphin-emu", "pcsx2", "ppsspp", "rpcs3", "ryujinx", "yuzu", "citra",
           "cemu", "xemu", "duckstation", "mgba", "flycast", "mame", "minetest", "luanti",
           "supertuxkart", "supertux", "0ad", "wesnoth", "openttd", "osu", "roblox", "vinegar",
           "gamehub", "playnite", "bottles", "minecraft", "tlauncher"],
    CHAT: ["telegram", "whatsapp", "signal", "element", "revolt", "guilded", "vesktop",
           "webcord", "armcord", "legcord", "caprine", "ferdium", "franz", "slack", "teams"],
    MEDIA: ["spotify", "freetube", "youtube", "netflix", "twitch", "streamlink", "stremio",
            "kodi", "jellyfin", "plex", "popcorn", "tiktok", "instagram", "reddit", "mpv", "celluloid"],
}
# Creative tools get media-ish categories but aren't distractions.
NOT_ENTERTAINMENT_CATEGORIES = {"AudioVideoEditing", "Mixer", "Settings", "Midi",
                                "Development", "IDE", "Graphics", "2DGraphics", "3DGraphics"}
GAME_FOLDER_NAMES = {"games", "Games", "GOG Games", "itch"}
SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", "snap", "Steam", "site-packages", ".git"}


def _known_category(*names):
    text = " ".join(n.lower() for n in names if n)
    for category, words in KNOWN.items():
        for w in words:
            if re.search(rf"(^|[^a-z0-9]){re.escape(w)}([^a-z0-9]|$)", text):
                return category
    return None


def _category_from_desktop(cats):
    """GAME / CHAT / MEDIA from a Categories= list, or None."""
    if any(c == "Game" or c.endswith("Game") for c in cats) and "System" not in cats:
        return GAME  # (an emulator like VirtualBox is tagged System/Emulator, not Game)
    if cats & {"Chat", "InstantMessaging", "IRCClient"} and "Development" not in cats:
        return CHAT
    if ("Player" in cats or "TV" in cats) and not cats & NOT_ENTERTAINMENT_CATEGORIES:
        return MEDIA  # players may also be tagged Recorder (VLC), so that's not excluded
    return None


def parse_desktop(path):
    """The [Desktop Entry] keys of a .desktop file (unlocalized), or None."""
    entry, in_main = {}, False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_main = line == "[Desktop Entry]"
                    continue
                if in_main and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    entry.setdefault(key.strip(), value.strip())
    except OSError:
        return None
    return entry or None


def resolve_exec(exec_line):
    """What an Exec= line launches: ("path", file) | ("flatpak", app_id) |
    ("steam", None) | ("snap", name) | None."""
    try:
        parts = shlex.split(exec_line)
    except ValueError:
        return None
    parts = [p for p in parts if not re.fullmatch(r"%[a-zA-Z]", p)]
    while parts and (parts[0] == "env" or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", parts[0])):
        parts.pop(0)
    if not parts:
        return None
    cmd = parts[0]
    base = os.path.basename(cmd)
    if base == "flatpak" and "run" in parts:
        for arg in parts[parts.index("run") + 1:]:
            if not arg.startswith("-"):
                return ("flatpak", arg.split("/")[0])
        return None
    if base == "steam" and any(a.startswith("steam://") for a in parts[1:]):
        return ("steam", None)
    path = cmd if cmd.startswith("/") else shutil.which(cmd)
    if not path:
        return None
    if path.startswith("/snap/"):
        return ("snap", os.path.basename(path))
    return ("path", path)


def _steam_library_games():
    names = set()
    for d in STEAM_DIRS:
        try:
            files = os.listdir(d)
        except OSError:
            continue
        for f in files:
            if not (f.startswith("appmanifest_") and f.endswith(".acf")):
                continue
            try:
                with open(os.path.join(d, f), encoding="utf-8", errors="replace") as fh:
                    m = re.search(r'"name"\s+"([^"]+)"', fh.read())
            except OSError:
                continue
            if m and not re.match(r"(Proton|Steam Linux Runtime|Steamworks|SteamVR)", m.group(1)):
                names.add(m.group(1))
    return names


def _walk_limited(root, max_depth):
    """Files under root, at most max_depth folders deep, skipping hidden
    and bulky folders."""
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS]
        if depth >= max_depth:
            dirnames[:] = []
        for name in filenames:
            yield dirpath, name


def _start_menu_shortcuts():
    """[(shortcut name, target path)] for the Start Menu's .lnk files, read
    with one PowerShell call (Windows has no simpler way to resolve them)."""
    script = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; $s = New-Object -ComObject WScript.Shell; "
        "Get-ChildItem -LiteralPath $args -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | "
        "ForEach-Object { $t = $s.CreateShortcut($_.FullName).TargetPath; "
        "if ($t) { $_.BaseName + [char]9 + $t } }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script,
                              *START_MENU_DIRS], capture_output=True, timeout=60,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pairs = []
    for line in out.decode("utf-8", "replace").splitlines():
        name, sep, target = line.strip().partition("\t")
        if sep and target.lower().endswith(".exe"):
            pairs.append((name, target))
    return pairs


def _scan_windows(ignored, home):
    custom_targets = {a.get("target") for a in load_custom_apps()}
    candidates = {}

    def consider(name, category, reason, target):
        rid = f"path:{target}"
        if rid in candidates or rid in ignored or target in custom_targets:
            return
        if os.path.basename(target).lower() in BUILTIN_NAMES or check_custom_path(target) is not None:
            return
        candidates[rid] = {"id": rid, "name": name, "category": category, "reason": reason,
                           "source": "path", "target": target, "kind": CATEGORY_KIND[category]}

    # 1. Start Menu shortcuts. No categories on Windows, so known names only.
    for name, target in _start_menu_shortcuts():
        category = _known_category(name, os.path.splitext(os.path.basename(target))[0])
        if category:
            consider(name, category, "A well-known entertainment app", target)

    # 2. Programs in folders called Games in your user folder.
    for dirpath, f in _walk_limited(home, 3):
        if f.lower().endswith(".exe") and any(
                part in GAME_FOLDER_NAMES for part in dirpath[len(home):].split(os.sep)):
            stem = os.path.splitext(f)[0]
            consider(stem, _known_category(stem) or GAME, "In a Games folder in your user folder",
                     os.path.join(dirpath, f))

    order = {GAME: 0, CHAT: 1, MEDIA: 2}
    recs = sorted(candidates.values(), key=lambda r: (order[r["category"]], r["name"].lower()))
    return {"recommendations": recs, "steam_games": sorted(_steam_library_games()), "snap_only": []}


def scan(ignored=(), home=HOME):
    """Look for entertainment apps. Returns
    {"recommendations": [...], "steam_games": [names], "snap_only": [names]}.

    Each recommendation: id, name, category, reason, source ("path" or
    "flatpak"), target, kind -- ready to become a custom app."""
    ignored = set(ignored)
    if plat.IS_WINDOWS:
        return _scan_windows(ignored, home)
    custom_targets = {a.get("target") for a in load_custom_apps()}
    candidates, steam_games, snap_only = {}, set(), set()

    def consider(name, category, reason, source, target):
        rid = f"{source}:{target}"
        if rid in candidates or rid in ignored or target in custom_targets:
            return
        if source == "flatpak":
            if target in HIDDEN_FLATPAKS or check_flatpak_id(target):
                return
        elif {os.path.basename(target).lower(), os.path.basename(os.path.realpath(target)).lower()} & BUILTIN_NAMES:
            return
        candidates[rid] = {"id": rid, "name": name, "category": category, "reason": reason,
                           "source": source, "target": target, "kind": CATEGORY_KIND[category]}

    # 1. App menu entries -- the richest source: they declare categories.
    for d in DESKTOP_DIRS:
        try:
            files = sorted(os.listdir(d))
        except OSError:
            continue
        for f in files:
            if not f.endswith(".desktop"):
                continue
            e = parse_desktop(os.path.join(d, f))
            if not e or e.get("Type", "Application") != "Application":
                continue
            if e.get("NoDisplay", "").lower() == "true" or e.get("Hidden", "").lower() == "true":
                continue
            name = e.get("Name", f[:-8])
            launch = resolve_exec(e.get("Exec", ""))
            if not launch:
                continue
            source, target = launch
            if source == "flatpak" and target in HIDDEN_FLATPAKS:
                continue
            cats = {c for c in e.get("Categories", "").split(";") if c}
            category = _category_from_desktop(cats)
            reason = f"Its menu entry is tagged {', '.join(sorted(c for c in cats if 'Game' in c or c in ('Chat', 'InstantMessaging', 'Player', 'TV'))) or category}"
            if category is None:
                category = _known_category(f[:-8], name, os.path.basename(target or ""))
                reason = "A well-known entertainment app"
            if category is None:
                continue
            if source == "steam":
                steam_games.add(name)
            elif source == "snap":
                if target.lower() not in BUILTIN_NAMES and target not in ("xonotic", "openspades", "steam"):
                    snap_only.add(name)
            else:
                consider(name, category, reason, source, target)

    # (/usr/games on its own isn't scanned: on Debian/Ubuntu it's mostly
    # terminal toys -- fortune, cowsay, bsdgames -- plus gamemoderun, which
    # Steam games use to launch. Real games there have menu entries above.)

    # 2. Your home folder: AppImages named like entertainment, and programs
    #    in folders called Games.
    for dirpath, f in _walk_limited(home, 3):
        path = os.path.join(dirpath, f)
        in_games_folder = any(part in GAME_FOLDER_NAMES for part in dirpath[len(home):].split("/"))
        is_appimage = f.lower().endswith(".appimage")
        if not (is_appimage or in_games_folder):
            continue
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            continue
        stem = re.split(r"[_\-. ](?=v?\d|x64|x86|linux|amd64)", re.sub(r"(?i)\.appimage$", "", f), maxsplit=1)[0]
        category = _known_category(stem, f)
        if in_games_folder and not f.lower().endswith((".so", ".dll", ".sh")):
            consider(stem, category or GAME, "In a Games folder in your home", "path", path)
        elif is_appimage and category:
            consider(stem, category, "An AppImage of a well-known entertainment app", "path", path)

    # 3. Steam library: covered whenever Steam itself is blocked.
    steam_games |= _steam_library_games()

    # Drop anything FocusLock won't block (system tools, desktop parts, core
    # packages) -- with one batched dpkg lookup instead of one per candidate.
    paths = [c["target"] for c in candidates.values() if c["source"] == "path"]
    core = core_package_paths(paths + [os.path.realpath(p) for p in paths])
    found = [c for c in candidates.values()
             if c["source"] == "flatpak" or check_custom_path(c["target"], home=home, core_paths=core) is None]

    order = {GAME: 0, CHAT: 1, MEDIA: 2}
    recs = sorted(found, key=lambda r: (order[r["category"]], r["name"].lower()))
    return {"recommendations": recs, "steam_games": sorted(steam_games), "snap_only": sorted(snap_only)}
