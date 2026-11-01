# PyInstaller spec for FocusLock on Windows (one folder, no console window).
# Build from the repo root:  pyinstaller packaging/windows/focuslock.spec --noconfirm
# The result (dist/FocusLock/) is what installer.iss packages.
import ast
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
    return names


a = Analysis(
    [os.path.join(ROOT, "focuslock_main.py")],
    pathex=[ROOT],
    datas=[(GUI, "."), (os.path.join(SPECPATH, "icon.ico"), ".")],
    hiddenimports=sorted(imports_of(GUI) | {"focuslock_win", "psutil", "sounddevice", "numpy", "winsound"}),
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
