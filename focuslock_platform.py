"""Everything that differs between Linux and Windows, in one place.

The rest of FocusLock imports its paths and OS-specific actions from here:
where the lock's state and the user's config live, how a privileged step
is run (sudo + the shell scripts on Linux; a UAC prompt + focuslock_win on
Windows), desktop notifications, and audio output. Nothing here imports a
GUI toolkit or focuslock_core at module level.
"""
import os
import subprocess
import sys
import tempfile

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)   # running from the PyInstaller build

if IS_WINDOWS:
    _PROGRAMDATA = os.environ.get("ProgramData") or r"C:\ProgramData"
    _LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    # Created and locked down (admins/SYSTEM write, users read) by focuslock_win.
    LOCKDIR = os.path.join(_PROGRAMDATA, "FocusLock")
    HOSTS_FILE = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows",
                              "System32", "drivers", "etc", "hosts")
    CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming"),
                              "FocusLock")
    STATE_DIR = os.path.join(_LOCALAPPDATA, "FocusLock")
    CACHE_DIR = os.path.join(_LOCALAPPDATA, "FocusLock", "cache")
    # Kept outside LOCKDIR so it outlives the lock (like /var/lib/focuslock-sitelog).
    SYSTEM_LOG_DIR = os.path.join(_PROGRAMDATA, "FocusLock-log")
    # Apps the guard task had to close: "<epoch>\t<app key>", same as attempts.log.
    GUARD_LOG = os.path.join(SYSTEM_LOG_DIR, "attempts.log")
    SITELOG_FILE = None
else:
    LOCKDIR = "/etc/focuslock"
    HOSTS_FILE = "/etc/hosts"
    CONFIG_DIR = os.path.expanduser("~/.config/focuslock")
    STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                             "focuslock")
    CACHE_DIR = os.path.expanduser("~/.cache/focuslock")
    GUARD_LOG = None
    SITELOG_FILE = "/var/lib/focuslock-sitelog/attempts.log"   # written by focuslock-sitelog.py

# Linux asks for the sudo password in FocusLock's own dialog; Windows shows
# its UAC prompt instead, so there's no password field.
NEEDS_PASSWORD = not IS_WINDOWS
# The dbus notification watcher (focuslock_watch.py) and its systemd user
# unit, and the root website logger, only exist on Linux. On Windows the
# blocker logs every attempt itself.
HAS_ATTEMPT_WATCHER = IS_LINUX
HAS_SITE_LOGGER = IS_LINUX

UAC_CANCELLED = "UAC_CANCELLED"


# ---------- running FocusLock's own entry points ----------

def self_command():
    """Command that runs FocusLock's multi-purpose entry point
    (focuslock_main.py), which takes --apply/--unlock/--blocked/... flags."""
    if FROZEN:
        return [sys.executable]
    exe = sys.executable
    if IS_WINDOWS and exe.lower().endswith("python.exe"):
        # pythonw has no console window to flash up.
        exe = exe[: -len("python.exe")] + "pythonw.exe"
    return [exe, os.path.join(SELF_DIR, "focuslock_main.py")]


def _detached_flags():
    if IS_WINDOWS:
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


# ---------- privileged steps ----------

_LINUX_SCRIPTS = {"apply": "focuslock-apply.sh", "youtube": "focuslock-youtube-break-apply.sh"}


def run_privileged(action, args, password=""):
    """Run a privileged step and wait for it. action is "apply" (start a lock)
    or "youtube" (the daily YouTube break); args is the list of positional
    arguments the Linux script takes (see focuslock-apply.sh), which the
    Windows helper accepts in the same order. Returns a CompletedProcess;
    on Windows a cancelled UAC prompt gives stderr == UAC_CANCELLED."""
    if IS_WINDOWS:
        return _run_elevated(action, args)
    from focuslock_core import privileged_script
    cmd = ["sudo", "-S", "-k", "bash", privileged_script(_LINUX_SCRIPTS[action]), *args]
    return subprocess.run(cmd, input=password + "\n", text=True, capture_output=True)


def _run_elevated(action, args):
    """Run `FocusLock --<action> <args.json>` through a UAC prompt and wait.
    An elevated process's output can't be piped back, so the helper writes
    its error text to <args.json>.err instead."""
    import ctypes
    import json
    from ctypes import wintypes

    fd, args_file = tempfile.mkstemp(prefix="focuslock-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(args, f)
    err_file = args_file + ".err"
    cmd = self_command() + [f"--{action}", args_file]

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
                    ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                    ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    SEE_MASK_NOCLOSEPROCESS, SEE_MASK_NO_CONSOLE, SW_HIDE = 0x40, 0x8000, 0
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NO_CONSOLE
    info.lpVerb = "runas"
    info.lpFile = cmd[0]
    info.lpParameters = subprocess.list2cmdline(cmd[1:])
    info.nShow = SW_HIDE
    shell32, kernel32 = ctypes.windll.shell32, ctypes.windll.kernel32
    try:
        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            error = ctypes.GetLastError()
            if error == 1223:   # ERROR_CANCELLED: "No" on the UAC prompt
                return subprocess.CompletedProcess(cmd, 1223, "", UAC_CANCELLED)
            return subprocess.CompletedProcess(cmd, error, "", ctypes.FormatError(error))
        kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        kernel32.CloseHandle(info.hProcess)
        try:
            with open(err_file, encoding="utf-8", errors="replace") as f:
                stderr = f.read()
        except OSError:
            stderr = ""
        return subprocess.CompletedProcess(cmd, code.value, "", stderr)
    finally:
        for path in (args_file, err_file):
            try:
                os.remove(path)
            except OSError:
                pass


# ---------- notifications ----------

def notify(title, message):
    """A desktop notification. Never raises."""
    try:
        if IS_WINDOWS:
            # A small popup of our own (focuslock_main --notify), so no
            # extra library or app registration is needed for toasts.
            subprocess.Popen(self_command() + ["--notify", title, message],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, **_detached_flags())
        else:
            subprocess.run(["notify-send", title, message], timeout=3)
    except Exception:
        pass


# ---------- audio ----------

def play_wav(path, linux_player):
    """Play a short WAV file without waiting. linux_player is the command
    focuslock_sound found (pw-play/paplay/aplay); unused on Windows."""
    if IS_WINDOWS:
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return
    subprocess.Popen(linux_player + [path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


class _PipeSink:
    """Raw 16-bit mono PCM into an external player's stdin (Linux)."""

    def __init__(self, cmd):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)

    def write(self, data):
        self.proc.stdin.write(data)

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


class _SoundDeviceSink:
    """Raw 16-bit mono PCM into the default output device (Windows)."""

    def __init__(self, rate):
        import sounddevice
        self.stream = sounddevice.RawOutputStream(samplerate=rate, channels=1, dtype="int16")
        self.stream.start()

    def write(self, data):
        try:
            self.stream.write(data)
        except Exception as e:   # PortAudioError etc.: let the player stop like a broken pipe
            raise OSError(str(e)) from e

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


def open_audio_sink(rate, linux_cmd):
    """(sink, None) for streaming 16-bit mono PCM, or (None, reason)."""
    if IS_WINDOWS:
        try:
            return _SoundDeviceSink(rate), None
        except Exception as e:  # sounddevice missing, or no output device
            return None, f"Couldn't start audio: {e}"
    if not linux_cmd:
        return None, "No audio player found (pw-cat, pacat or aplay)."
    try:
        return _PipeSink(linux_cmd), None
    except OSError as e:
        return None, f"Couldn't start audio: {e}"
