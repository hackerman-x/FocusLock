# PyInstaller spec for FocusLock on Windows (one folder, no console window).
# Build from the repo root:  pyinstaller packaging/windows/focuslock.spec --noconfirm
# The result (dist/FocusLock/) is what installer.iss packages.
import ast
import importlib.util
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
GUI = os.path.join(ROOT, "focuslock-gui.py")


def imports_of(path):
    """Every module a script imports. focuslock_main.py runs the GUI with
    runpy (its file name has a dash), which PyInstaller can't follow."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {n.name for n in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            # "from tkinter import filedialog" needs tkinter.filedialog too, or the frozen
            # app crashes with "cannot import name 'filedialog' from 'tkinter'"
            for alias in node.names:
                sub = f"{node.module}.{alias.name}"
                try:
                    if importlib.util.find_spec(sub):
                        names.add(sub)
                except (ImportError, ValueError):
                    pass
    return names


a = Analysis(
    [os.path.join(ROOT, "focuslock_main.py")],
    pathex=[ROOT],
    datas=[(GUI, "."), (os.path.join(SPECPATH, "icon.ico"), ".")],
    hiddenimports=sorted(imports_of(GUI) | {"focuslock_win", "psutil", "sounddevice", "numpy", "winsound",
                                            "tkinter.filedialog", "tkinter.font"}),
    excludes=["webview", "gi"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FocusLock",
    console=False,
    icon=os.path.join(SPECPATH, "icon.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="FocusLock")
