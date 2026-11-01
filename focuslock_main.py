#!/usr/bin/env python3
"""FocusLock's single entry point (what FocusLock.exe runs on Windows).

  (no args)   open the FocusLock window
  --watch     the background attempt logger (Linux; see focuslock_watch.py)
  --apply, --youtube, --unlock, --reblock, --guard, --blocked, --notify
              Windows lock steps -- see focuslock_win.py
"""
import os
import runpy
import sys

# PyInstaller unpacks bundled files under sys._MEIPASS.
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
WIN_FLAGS = {"--apply", "--youtube", "--unlock", "--reblock", "--guard", "--blocked", "--notify"}


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in WIN_FLAGS:
        import focuslock_win
        sys.exit(focuslock_win.main(argv))
    if argv and argv[0] == "--watch":
        sys.argv = [os.path.join(HERE, "focuslock_watch.py"), *argv[1:]]
        runpy.run_path(sys.argv[0], run_name="__main__")
        return
    sys.argv = [os.path.join(HERE, "focuslock-gui.py"), *argv]
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()
