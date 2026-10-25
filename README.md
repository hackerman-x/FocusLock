# FocusLock
Lock away distracting apps and websites so you can focus.

Pick how long to focus and what to block, and FocusLock locks it in. There is
**no early-unlock button** on purpose: the lock lifts by itself when the time
is up.

## Download

Get the AppImage from the [Releases](https://github.com/hackerman-x/FocusLock/releases) page, then:

```bash
chmod +x FocusLock.AppImage
./FocusLock.AppImage
```

## What it does

- **Blocks apps**: games, launchers and other distractions (including Steam
  games, Flatpaks and snaps). Opening one shows a "blocked" notification instead.
- **Blocks websites** through `/etc/hosts`, with built-in groups plus your own sites.
- **Daily YouTube break**: one hour of YouTube per day during a lock, re-blocked
  automatically. The optional browser extension in `youtube-extension/` limits
  that hour to videos you approved beforehand.
- **Stats**: a log of blocked attempts, streaks, badges and a Pomodoro planner.
- **Ambient sounds**: rain, noise colours and more, generated on the fly (no audio files).
- **App scan**: suggests installed apps worth blocking. It only reads, and never blocks anything by itself.

Starting a lock needs your sudo password. FocusLock passes it straight to
`sudo` and never stores or sends it anywhere.

## Running from source

Works on Debian/Ubuntu and Arch Linux.

```bash
# Ubuntu/Debian: sudo apt install python3-tk python3-gi
# Arch:          sudo pacman -S tk python-gobject
python3 -m venv venv --system-site-packages
venv/bin/pip install -r requirements.txt
venv/bin/python focuslock-gui.py      # Tkinter app
venv/bin/python focuslock-webui.py    # web UI (pywebview)
```

`lock.sh` starts a 2-day lock from the terminal with everything blocked.

## Files

| File | Purpose |
|---|---|
| `focuslock-gui.py`, `focuslock-webui.py` + `webui/` | The two interfaces |
| `focuslock_core.py` | Shared logic: settings, block lists, stats |
| `focuslock-apply.sh` | Applies a lock (run as root via sudo) |
| `focuslock-unlock.sh` | Lifts the lock when the timer ends |
| `focuslock-youtube-*.sh` | The daily YouTube break |
| `focuslock-sitelog.py`, `focuslock_watch.py` | Count blocked website and app attempts |
| `focuslock_scan.py`, `focuslock_ambient.py`, `focuslock_sound.py`, `focuslock_anim.py` | App scan, sounds, animations |
| `packaging/` | AppImage launcher (`AppRun`) and desktop entry |

## Note

Some built-in app paths in `focuslock-apply.sh` and `focuslock_core.py` point
at the author's home folder (for example Stardew Valley, Godot and Aseprite).
On other machines those entries are simply skipped; add your own apps from the
app's custom-apps list.
