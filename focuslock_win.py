"""FocusLock's privileged steps on Windows -- the counterpart of
focuslock-apply.sh, focuslock-unlock.sh and the focuslock-youtube-*.sh
scripts. Run through focuslock_main.py:

  --apply ARGS.json    start a lock (elevated, via the UAC prompt)
  --youtube ARGS.json  the daily one-hour YouTube break (elevated)
  --unlock             lift the lock once its time is up (SYSTEM task)
  --reblock            end the YouTube break (SYSTEM task)
  --guard              close blocked apps that got past the launch block (SYSTEM task)
  --blocked KEY ...    what Windows runs instead of a blocked app (as you)

How a lock works here:
  * Websites: the same "# FOCUSLOCK-START ... END" block in the hosts file.
  * Apps, layer 1: an "Image File Execution Options" registry key per
    program file name whose Debugger value is `FocusLock.exe --blocked KEY`,
    so Windows starts the blocker instead of the app.
  * Apps, layer 2: a SYSTEM guard task that closes any blocked program that
    still got started (e.g. Store apps, or names with a *), and puts the
    hosts block and registry keys back if they're removed.
  * Unlock: a SYSTEM scheduled task at the unlock time (also run at boot
    and when missed, like systemd's Persistent=true) that undoes all of it.

The ARGS.json files hold the same positional arguments the Linux scripts
take. Everything in them is re-checked here before anything is touched.
Error text for the GUI goes to ARGS.json.err (an elevated process's output
can't be piped back to it).
"""
import fnmatch
import json
import ntpath
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from xml.sax.saxutils import escape

import focuslock_core as core
import focuslock_platform as plat

LOCKDIR = plat.LOCKDIR
HOSTS = plat.HOSTS_FILE
SYSTEM_LOG_DIR = getattr(plat, "SYSTEM_LOG_DIR", None)
GUARD_LOG = plat.GUARD_LOG

# Files in LOCKDIR, besides the ones core reads (unlock_at, locked_at,
# selected_apps, selected_domains, intent, youtube_break_*):
#   unlock_epoch / youtube_break_until_epoch   the same times as epochs
#   domains.json   every domain this lock blocks
#   guard.json     {app key: [file name patterns]} for the guard task
#   ifeo.json      the registry changes to undo at unlock


def _p(name):
    """A file in the lock folder (looked up each time, so tests can move it)."""
    return os.path.join(LOCKDIR, name)


TASK_FOLDER = "FocusLock"
TASK_UNLOCK = TASK_FOLDER + "\\Unlock"
TASK_GUARD = TASK_FOLDER + "\\Guard"
TASK_REBLOCK = TASK_FOLDER + "\\YouTubeReblock"

IFEO_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
BLOCK_ADDRS = ("0.0.0.0", "::")
YT_DOMAINS = core.DOMAIN_GROUPS["youtube"]
START, END = "# FOCUSLOCK-START (auto-removed at unlock)", "# FOCUSLOCK-END"

GUARD_INTERVAL = 2          # seconds between checks for blocked programs
GUARD_REPAIR_INTERVAL = 30  # seconds between checks that the block is still in place


class LockError(Exception):
    """A reason to refuse, shown to the user as is."""


# ---------- small helpers (stubbed out by the tests) ----------

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read(path):
    return core.read_file(path)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _dump(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _now():
    return time.time()


def install_dir():
    return os.path.join(os.environ.get("ProgramFiles") or r"C:\Program Files", "FocusLock")


def require_installed():
    """SYSTEM tasks run FocusLock.exe, so it must be the installed copy in
    Program Files, which ordinary users can't change. A copy in Downloads
    could be swapped for anything, which would then run as SYSTEM."""
    exe = os.path.normcase(os.path.abspath(sys.executable))
    if not (plat.FROZEN and exe.startswith(os.path.normcase(install_dir()) + os.sep)):
        raise LockError("Install FocusLock with its installer to start a lock "
                        "(it has to run from Program Files).")
    return sys.executable


def lock_dirs():
    """Create LOCKDIR and the log folder, writable only by admins and SYSTEM."""
    for d in (LOCKDIR, SYSTEM_LOG_DIR):
        if not d:
            continue
        os.makedirs(d, exist_ok=True)
        _run(["icacls", d, "/inheritance:r", "/grant:r",
              "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-32-545:(OI)(CI)RX"])


def flush_dns():
    _run(["ipconfig", "/flushdns"])


# ---------- hosts file ----------

def _hosts_lines(domains):
    return [f"{addr} {d}" for d in domains for addr in BLOCK_ADDRS]


def hosts_add_block(text, domains):
    """text with a FocusLock block for domains appended (unchanged if it has one)."""
    if "# FOCUSLOCK-START" in text or not domains:
        return text
    nl = "\r\n" if "\r\n" in text or not text else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += nl
    return text + nl.join([START, *_hosts_lines(domains), END]) + nl


def hosts_remove_block(text):
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith("# FOCUSLOCK-START"):
            inside = True
        elif inside and line.startswith(END):
            inside = False
        elif not inside:
            out.append(line)
    return "".join(out)


def hosts_remove_domains(text, domains):
    """Drop just these domains' lines (the YouTube break), keeping the block."""
    drop = {f"{addr} {d}" for d in domains for addr in (*BLOCK_ADDRS, core.SITELOG_ADDR)}
    return "".join(line for line in text.splitlines(keepends=True) if line.strip() not in drop)


def hosts_add_domains(text, domains):
    """Put these domains' lines back inside an existing block (end of the break)."""
    present = {line.strip() for line in text.splitlines()}
    missing = [line for line in _hosts_lines(domains) if line not in present]
    if not missing or END not in text:
        return text
    nl = "\r\n" if "\r\n" in text else "\n"
    i = text.index(END)
    return text[:i] + "".join(m + nl for m in missing) + text[i:]


def _edit_hosts(change):
    # latin-1 round-trips any bytes unchanged, whatever encoding the file is in.
    try:
        with open(HOSTS, encoding="latin-1", newline="") as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    new = change(text)
    if new != text:
        with open(HOSTS, "w", encoding="latin-1", newline="") as f:
            f.write(new)
        flush_dns()


# ---------- registry (Image File Execution Options) ----------

def _views():
    import winreg
    return (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)


def debugger_command(exe, key):
    return subprocess.list2cmdline([exe, "--blocked", key])


def ifeo_block(name, command):
    """Point name's Debugger at the blocker; returns what to undo later."""
    import winreg
    records = []
    for view in _views():
        sub = f"{IFEO_PATH}\\{name}"
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0, winreg.KEY_ALL_ACCESS | view)
            existed = True
        except FileNotFoundError:
            k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, sub, 0, winreg.KEY_ALL_ACCESS | view)
            existed = False
        with k:
            try:
                old = winreg.QueryValueEx(k, "Debugger")[0]
            except FileNotFoundError:
                old = None
            if old == command:
                continue   # already ours (repair pass)
            winreg.SetValueEx(k, "Debugger", 0, winreg.REG_SZ, command)
        records.append({"name": name, "view": view, "existed": existed, "old": old})
    return records


def ifeo_restore(record):
    import winreg
    sub = f"{IFEO_PATH}\\{record['name']}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0,
                            winreg.KEY_ALL_ACCESS | record["view"]) as k:
            if record["old"] is not None:
                winreg.SetValueEx(k, "Debugger", 0, winreg.REG_SZ, record["old"])
            else:
                try:
                    winreg.DeleteValue(k, "Debugger")
                except FileNotFoundError:
                    pass
        if not record["existed"]:
            try:
                winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, sub, record["view"])
            except OSError:
                pass   # something else added values meanwhile: leave the key
    except FileNotFoundError:
        pass


def ifeo_sweep():
    """Remove any Debugger value of ours left behind (e.g. a lost manifest)."""
    import winreg
    for view in _views():
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, IFEO_PATH, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            names, i = [], 0
            while True:
                try:
                    names.append(winreg.EnumKey(root, i))
                except OSError:
                    break
                i += 1
        for name in names:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{IFEO_PATH}\\{name}", 0,
                                    winreg.KEY_ALL_ACCESS | view) as k:
                    value = winreg.QueryValueEx(k, "Debugger")[0]
                    if "focuslock" in value.lower() and "--blocked" in value:
                        winreg.DeleteValue(k, "Debugger")
            except OSError:
                pass


# ---------- scheduled tasks ----------

def task_xml(description, command, arguments, at=None, boot=False, forever=False):
    """Task Scheduler XML for a SYSTEM task. at is a local
    'YYYY-MM-DD HH:MM:SS' time; boot also runs it at every startup."""
    triggers = []
    if at:
        triggers.append(f"<TimeTrigger><StartBoundary>{at.replace(' ', 'T')}</StartBoundary>"
                        "<Enabled>true</Enabled></TimeTrigger>")
    if boot:
        triggers.append("<BootTrigger><Enabled>true</Enabled></BootTrigger>")
    restart = ("<RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>"
               if forever else "")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>{escape(description)}</Description></RegistrationInfo>
  <Triggers>{''.join(triggers)}</Triggers>
  <Principals><Principal id="Author"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>{'PT0S' if forever else 'PT10M'}</ExecutionTimeLimit>
    {restart}
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(command)}</Command><Arguments>{escape(arguments)}</Arguments></Exec></Actions>
</Task>
"""


def create_task(name, xml):
    path = _p(name.rsplit("\\", 1)[-1] + ".xml")
    with open(path, "w", encoding="utf-16") as f:
        f.write(xml)
    result = _run(["schtasks", "/Create", "/TN", name, "/XML", path, "/F"])
    os.remove(path)
    if result.returncode != 0:
        raise LockError(f"Couldn't create the {name} task: {result.stderr.strip() or result.stdout.strip()}")


def delete_task(name):
    _run(["schtasks", "/Delete", "/TN", name, "/F"])


# ---------- lock state ----------

def unlock_epoch():
    text = _read(_p("unlock_epoch"))
    return int(text) if text and text.isdigit() else core.parse_unlock_time(_read(_p("unlock_at")))


def lock_active():
    return _read(_p("unlock_at")) is not None


def youtube_break_active():
    until = _read(_p("youtube_break_until_epoch"))
    return bool(until and until.isdigit() and _now() < int(until))


def _csv(text):
    return [] if text in ("", "none") else ["all"] if text == "all" else text.split(",")


def _selected(key, keys):
    return keys == ["all"] or key in keys


def plan_lock(apps_csv, domains_csv, custom_defs, custom_sites):
    """What to block: (applied app keys, {key: [file patterns]},
    applied domain keys, [domains]). Custom entries are validated with the
    same rules the GUI uses; anything invalid is skipped, not blocked."""
    app_keys, domain_keys = _csv(apps_csv), _csv(domains_csv)
    guard, applied_apps = {}, []
    for key, _label in core.APPS:
        if _selected(key, app_keys) and key in core.WIN_APP_EXES:
            guard[key] = list(core.WIN_APP_EXES[key])
            applied_apps.append(key)
    for line in (custom_defs or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 4 or not re.fullmatch(r"c_[a-z0-9_]{1,40}", parts[0]):
            continue
        key, _name, source, target = parts
        if _selected(key, app_keys) and source == "path" and core.check_custom_path(target) is None:
            guard[key] = [ntpath.basename(target)]   # ntpath: Windows paths even when tested on Linux
            applied_apps.append(key)

    applied_domains, domains = [], []
    for key, ds in core.DOMAIN_GROUPS.items():
        if _selected(key, domain_keys):
            applied_domains.append(key)
            domains += ds
    for line in (custom_sites or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not re.fullmatch(r"w_[a-z0-9_]{1,40}", parts[0]):
            continue
        if not _selected(parts[0], domain_keys):
            continue
        ok = [d for d in parts[2].split() if core.check_domain(d) is None]
        if ok:
            applied_domains.append(parts[0])
            domains += ok
    return applied_apps, guard, applied_domains, list(dict.fromkeys(domains))


# ---------- the steps ----------

def apply(args):
    unlock_human, unlock_calendar, apps_csv, domains_csv, intent, custom_defs, custom_sites = \
        (list(args) + [""] * 7)[:7]
    exe = require_installed()
    ends = core.parse_unlock_time(unlock_calendar)
    if ends is None or ends <= _now():
        raise LockError("The unlock time is missing or already past.")
    if lock_active():
        raise LockError("A lock is already active.")
    applied_apps, guard, applied_domains, domains = plan_lock(apps_csv, domains_csv,
                                                              custom_defs, custom_sites)
    lock_dirs()
    try:
        _start_lock(exe, unlock_human, unlock_calendar, ends, intent,
                    applied_apps, guard, applied_domains, domains)
    except Exception:
        unlock(force=True)   # never leave half a lock behind
        raise


def _start_lock(exe, unlock_human, unlock_calendar, ends, intent,
                applied_apps, guard, applied_domains, domains):
    _write(_p("unlock_at"), unlock_human + "\n")
    _write(_p("unlock_epoch"), f"{ends}\n")
    _write(_p("locked_at"), f"{int(_now())}\n")
    _write(_p("selected_apps"), "".join(k + "\n" for k in applied_apps))
    _write(_p("selected_domains"), "".join(k + "\n" for k in applied_domains))
    if intent:
        _write(_p("intent"), intent + "\n")
    _dump(_p("domains.json"), domains)
    _dump(_p("guard.json"), guard)

    # The unlock task first, so whatever happens below the lock still ends on time.
    create_task(TASK_UNLOCK, task_xml("FocusLock - lift the lock when its time is up",
                                      exe, "--unlock", at=unlock_calendar, boot=True))
    _edit_hosts(lambda text: hosts_add_block(text, domains))
    block_apps(exe, guard)
    create_task(TASK_GUARD, task_xml("FocusLock - keep blocked apps closed during a lock",
                                     exe, "--guard", boot=True, forever=True))
    _run(["schtasks", "/Run", "/TN", TASK_GUARD])


def block_apps(exe, guard):
    records = _load(_p("ifeo.json"), [])
    for key, patterns in guard.items():
        for name in sorted(core.win_exe_names(patterns)):
            records += ifeo_block(name, debugger_command(exe, key))
    _dump(_p("ifeo.json"), records)


def unlock(force=False):
    """Undo the lock. Run by the unlock task (also at boot, when it's
    usually too early: then it does nothing) and by the guard if the
    task somehow didn't."""
    ends = unlock_epoch()
    if not force and lock_active() and ends is not None and _now() < ends:
        return False
    _edit_hosts(hosts_remove_block)
    for record in reversed(_load(_p("ifeo.json"), [])):
        ifeo_restore(record)
    ifeo_sweep()
    for task in (TASK_REBLOCK, TASK_GUARD, TASK_UNLOCK):
        delete_task(task)
    shutil.rmtree(LOCKDIR, ignore_errors=True)
    return True


def youtube_break(args):
    reblock_human, reblock_calendar = (list(args) + ["", ""])[:2]
    exe = require_installed()
    if not lock_active():
        raise LockError("No FocusLock is currently active.")
    today = date.today().isoformat()
    if _read(_p("youtube_break_last_used")) == today:
        raise LockError("Today's YouTube break has already been used. Resets at midnight.")
    until = core.parse_unlock_time(reblock_calendar)
    if until is None or not 0 < until - _now() <= 3700:
        raise LockError("The break must end within the hour.")
    _write(_p("youtube_break_last_used"), today + "\n")
    _write(_p("youtube_break_until"), reblock_human + "\n")
    _write(_p("youtube_break_until_epoch"), f"{until}\n")
    _edit_hosts(lambda text: hosts_remove_domains(text, YT_DOMAINS))
    create_task(TASK_REBLOCK, task_xml("FocusLock - re-block YouTube after the daily break",
                                       exe, "--reblock", at=reblock_calendar))


def reblock():
    if lock_active() and any(d in _load(_p("domains.json"), []) for d in YT_DOMAINS):
        _edit_hosts(lambda text: hosts_add_domains(text, YT_DOMAINS))
    try:
        os.remove(_p("youtube_break_until_epoch"))
    except OSError:
        pass
    delete_task(TASK_REBLOCK)


def _log_attempt(path, key):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{int(_now())}\t{key}\n")
    except OSError:
        pass


def match_blocked(name, guard):
    """The app key whose patterns match a running program's file name, or None."""
    low = (name or "").lower()
    for key, patterns in guard.items():
        if any(fnmatch.fnmatchcase(low, p.lower()) for p in patterns):
            return key
    return None


def repair(exe, guard):
    """Put the hosts block and registry keys back if someone removed them."""
    domains = _load(_p("domains.json"), [])
    if youtube_break_active():
        domains = [d for d in domains if d not in YT_DOMAINS]
    _edit_hosts(lambda text: hosts_add_block(text, domains))
    if not youtube_break_active() and _read(_p("youtube_break_until_epoch")):
        reblock()   # the re-block task was missed (e.g. the PC was asleep)
    block_apps(exe, guard)


def guard_loop():
    import psutil
    exe = sys.executable
    guard = _load(_p("guard.json"), {})
    last_repair = 0.0
    while lock_active():
        ends = unlock_epoch()
        if ends is not None and _now() >= ends:
            unlock()
            return
        for proc in psutil.process_iter(["name"]):
            key = match_blocked(proc.info.get("name"), guard)
            if key:
                try:
                    proc.kill()
                    _log_attempt(GUARD_LOG, key)
                except psutil.Error:
                    pass
        if _now() - last_repair >= GUARD_REPAIR_INTERVAL:
            last_repair = _now()
            try:
                repair(exe, guard)
            except OSError:
                pass
        time.sleep(GUARD_INTERVAL)


# ---------- entry points (see focuslock_main.py) ----------

def run_with_args_file(step, args_file):
    """Run apply/youtube_break with the GUI's ARGS.json; errors go to ARGS.json.err."""
    try:
        with open(args_file, encoding="utf-8") as f:
            args = json.load(f)
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise LockError("Bad arguments.")
        step(args)
        return 0
    except Exception as e:
        message = str(e) if isinstance(e, LockError) else f"{type(e).__name__}: {e}"
        try:
            _write(args_file + ".err", message)
        except OSError:
            pass
        return 1


def blocked(key):
    """What Windows starts instead of a blocked app (runs as you)."""
    if re.fullmatch(r"[a-z0-9_]{1,48}", key):
        os.makedirs(os.path.dirname(core.attempts_path()), exist_ok=True)
        _log_attempt(core.attempts_path(), key)
    names = dict(core.all_apps())
    until = _read(_p("unlock_at")) or "the lock ends"
    show_popup("FocusLock", f"{names.get(key, 'This app')} is blocked until {until}")
    return 1


def show_popup(title, message, seconds=6):
    """A small always-on-top notice in the bottom-right corner."""
    import tkinter as tk
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#ff2e88")
    body = tk.Frame(root, bg="#0b0616", padx=16, pady=12)
    body.pack(padx=2, pady=2)
    tk.Label(body, text=title, bg="#0b0616", fg="#ff2e88", font=("Segoe UI", 11, "bold"),
             anchor="w").pack(fill="x")
    tk.Label(body, text=message, bg="#0b0616", fg="#f4eefc", font=("Segoe UI", 10),
             wraplength=320, justify="left", anchor="w").pack(fill="x", pady=(4, 0))
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f"+{root.winfo_screenwidth() - w - 24}+{root.winfo_screenheight() - h - 64}")
    for widget in (root, body, *body.winfo_children()):
        widget.bind("<Button-1>", lambda _e: root.destroy())
    root.after(seconds * 1000, root.destroy)
    root.mainloop()


def main(argv):
    flag = argv[0] if argv else ""
    if flag == "--apply" and len(argv) >= 2:
        return run_with_args_file(apply, argv[1])
    if flag == "--youtube" and len(argv) >= 2:
        return run_with_args_file(youtube_break, argv[1])
    if flag == "--unlock":
        unlock()
        return 0
    if flag == "--reblock":
        reblock()
        return 0
    if flag == "--guard":
        guard_loop()
        return 0
    if flag == "--blocked" and len(argv) >= 2:
        return blocked(argv[1])
    if flag == "--notify" and len(argv) >= 3:
        show_popup(argv[1], argv[2])
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
