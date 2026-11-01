# FocusLock on Windows

## Install

Download `FocusLock-Setup.exe` from the
[Releases](https://github.com/hackerman-x/FocusLock/releases) page and run it.
FocusLock installs to `C:\Program Files\FocusLock`, with no choice of folder
(see "Why Program Files" below). Starting a lock shows Windows' administrator
prompt; there's no password to type into FocusLock itself.

Windows 10 and 11 (64-bit) are supported.

## How a lock works

| | Windows | Linux equivalent |
|---|---|---|
| Websites | A `# FOCUSLOCK-START … END` block in `C:\Windows\System32\drivers\etc\hosts` | `/etc/hosts` |
| Apps (when you open one) | An *Image File Execution Options* registry key per program file name, so Windows starts FocusLock's "blocked" notice instead | A wrapper script swapped in for the program |
| Apps (already running, Store apps, `Godot*.exe`-style names) | A **guard** task (runs as SYSTEM) closes them every 2 seconds, and puts the hosts block and registry keys back if they're removed | – |
| Lifting the lock | A scheduled task (SYSTEM) at the unlock time. It also runs at startup and if the PC was off, but never lifts a lock early | systemd timer |
| Lock state | `C:\ProgramData\FocusLock` (only admins can change it) | `/etc/focuslock` |
| Your stats and settings | `%APPDATA%\FocusLock` | `~/.config/focuslock` |
| Distraction log | `%LOCALAPPDATA%\FocusLock\attempts.log` plus `C:\ProgramData\FocusLock-log\attempts.log` (the guard's) | `~/.local/state/focuslock/attempts.log` |

Like on Linux, there is no early unlock. Updating or uninstalling FocusLock
is refused while a lock is active.

### Why Program Files

The guard and unlock tasks run as SYSTEM, so the program they start must be
one that ordinary users can't change. FocusLock refuses to start a lock if
it isn't running from its installed location.

### Not on Windows (yet)

- Counting attempts to open blocked **websites**. They're still blocked, but not counted.
- The web UI (`focuslock-webui.py`). Windows ships the regular window only.
- Flatpak and snap app sources (Linux-only).

### Blocking is by file name

Windows blocks programs by their `.exe` name. Blocking a custom app called
`game.exe` blocks every program with that name. FocusLock refuses names that
Windows itself needs (Explorer, Task Manager, PowerShell, and so on).

## Building it yourself

On Windows with Python 3.12:

```
pip install -r requirements-windows.txt pyinstaller pytest
python -m pytest tests
pyinstaller packaging/windows/focuslock.spec --noconfirm
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\installer.iss
```

The installer ends up in `dist\FocusLock-Setup.exe`.

## Automatic checks

`.github/workflows/windows.yml` runs on every push and pull request, on
GitHub's Windows machines:

1. Unit tests (`tests/`).
2. Builds the exe and installer, and uploads the installer as a download.
3. Installs it, opens the window for 15 seconds and takes a screenshot.
4. Runs `packaging/windows/e2e_test.py`, which starts a real 5-minute lock. It checks:
   - the hosts block and registry keys are in place;
   - a blocked program shows the notice and is logged;
   - the guard closes a program the registry can't block;
   - `--unlock` before the time does nothing;
   - the YouTube break, and its once-a-day limit;
   - the guard repairs a tampered hosts file;
   - the lock lifts by itself on time and leaves nothing behind.

Pushing a `v*` tag also attaches the installer to that GitHub release.
