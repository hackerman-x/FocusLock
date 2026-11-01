"""End-to-end lock test on a real Windows machine, against the installed
FocusLock (C:\\Program Files\\FocusLock). Needs admin rights -- GitHub's
windows-latest runners have them -- and changes the hosts file, registry
and Task Scheduler for a few minutes, then checks that unlock puts every
one of them back. Run with: python packaging/windows/e2e_test.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import winreg
from datetime import datetime

EXE = r"C:\Program Files\FocusLock\FocusLock.exe"
LOCKDIR = r"C:\ProgramData\FocusLock"
GUARD_LOG = r"C:\ProgramData\FocusLock-log\attempts.log"
USER_LOG = os.path.join(os.environ["LOCALAPPDATA"], "FocusLock", "attempts.log")
HOSTS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")
IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
SYS32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")

TEST_DIR = os.path.join(os.path.expanduser("~"), "focuslock-e2e")
TEST_APP = os.path.join(TEST_DIR, "FocusLockTestApp.exe")   # whoami.exe: blocked at launch (registry)
GUARDED = os.path.join(TEST_DIR, "Godot_e2e.exe")            # ping.exe: Godot*.exe has no registry key,
                                                             # so only the guard task can stop it
LOCK_SECONDS = 300


def step(message):
    print(f"\n== {message}", flush=True)


def check(condition, message):
    if not condition:
        sys.exit(f"FAIL: {message}")
    print(f"  ok: {message}", flush=True)


def wait_for(condition, seconds, message):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            print(f"  ok: {message}", flush=True)
            return
        time.sleep(1)
    sys.exit(f"FAIL (after {seconds}s): {message}")


def stamp(epoch):
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def hosts_text():
    with open(HOSTS, encoding="latin-1") as f:
        return f.read()


def task_exists(name):
    return subprocess.run(["schtasks", "/Query", "/TN", name], capture_output=True).returncode == 0


def ifeo_debugger(name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{IFEO}\\{name}", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "Debugger")[0]
    except OSError:
        return None


def blocked_by_hosts(domain):
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(domain, 443)}
    except socket.gaierror:
        return True
    return addrs <= {"0.0.0.0", "::"}


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def run_step(flag, args):
    """Run FocusLock.exe --apply/--youtube with an args file, like the GUI does
    (minus the UAC prompt: this is already elevated)."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(args, f)
    code = subprocess.run([EXE, flag, path], timeout=120).returncode
    return code, read(path + ".err")


def main():
    check(os.path.exists(EXE), "FocusLock is installed")
    os.makedirs(TEST_DIR, exist_ok=True)
    shutil.copy(os.path.join(SYS32, "whoami.exe"), TEST_APP)
    shutil.copy(os.path.join(SYS32, "PING.EXE"), GUARDED)
    check(subprocess.run([TEST_APP], capture_output=True).returncode == 0, "the test app runs before the lock")

    step("start a lock")
    ends = time.time() + LOCK_SECONDS
    code, err = run_step("--apply", [
        f"Test, {stamp(ends)}", stamp(ends), "godot,c_e2e", "youtube,w_example", "e2e test",
        f"c_e2e\tE2E Test App\tpath\t{TEST_APP}", "w_example\tExample\texample.com www.example.com",
    ])
    check(code == 0, f"--apply succeeded {err!r}")
    check(read(os.path.join(LOCKDIR, "selected_apps")).split() == ["godot", "c_e2e"], "manifest lists the apps")
    check(task_exists(r"FocusLock\Unlock") and task_exists(r"FocusLock\Guard"), "unlock and guard tasks exist")
    check("--blocked c_e2e" in (ifeo_debugger("FocusLockTestApp.exe") or ""), "registry blocks the test app")
    check("0.0.0.0 example.com" in hosts_text(), "hosts file blocks example.com")
    check(blocked_by_hosts("example.com"), "example.com no longer resolves")

    step("blocked apps")
    code = subprocess.run([TEST_APP], timeout=60).returncode
    check(code == 1, "launching the test app runs the blocker instead")
    check("\tc_e2e" in read(USER_LOG), "the attempt is logged")
    guarded = subprocess.Popen([GUARDED, "-n", "120", "127.0.0.1"], stdout=subprocess.DEVNULL)
    wait_for(lambda: guarded.poll() is not None, 30, "the guard closes a program the registry can't block")
    check("\tgodot" in read(GUARD_LOG), "the guard logs it")

    step("no early unlock")
    subprocess.run([EXE, "--unlock"], timeout=60)
    check(os.path.exists(os.path.join(LOCKDIR, "unlock_at")), "--unlock before the time does nothing")

    step("daily YouTube break")
    code, err = run_step("--youtube", [f"Test, {stamp(time.time() + 45)}", stamp(time.time() + 45)])
    check(code == 0, f"--youtube succeeded {err!r}")
    check("youtube.com" not in hosts_text(), "YouTube is unblocked")
    code, err = run_step("--youtube", [f"Test, {stamp(time.time() + 45)}", stamp(time.time() + 45)])
    check(code == 1 and "already been used" in err, "a second break the same day is refused")

    step("tampering")
    with open(HOSTS, "w", encoding="latin-1") as f:
        f.write(hosts_text().split("# FOCUSLOCK-START")[0])
    wait_for(lambda: "0.0.0.0 example.com" in hosts_text(), 60, "the guard puts the hosts block back")
    wait_for(lambda: "0.0.0.0 youtube.com" in hosts_text(), 90, "YouTube is re-blocked after the break")

    step("unlock on time")
    wait_for(lambda: not os.path.exists(LOCKDIR), int(ends - time.time()) + 150, "the lock lifts by itself")
    check(time.time() >= ends - 1, "not before its time")
    check("FOCUSLOCK" not in hosts_text(), "hosts file is clean")
    check(ifeo_debugger("FocusLockTestApp.exe") is None, "registry key removed")
    check(not task_exists(r"FocusLock\Unlock") and not task_exists(r"FocusLock\Guard"), "tasks removed")
    check(subprocess.run([TEST_APP], capture_output=True).returncode == 0, "the test app runs again")
    check(not blocked_by_hosts("example.com"), "example.com resolves again")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    print("\nAll end-to-end checks passed.")


if __name__ == "__main__":
    main()
