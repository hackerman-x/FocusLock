"""focuslock_win's logic, with every Windows system call stubbed out, so
these run on Linux too. The real registry/Task Scheduler/hosts behaviour
is covered by packaging/windows/e2e_test.py on a Windows CI machine."""
import json
import os
import xml.etree.ElementTree as ET
from datetime import date

import pytest

import focuslock_core as core
import focuslock_win as win

EXE = r"C:\Program Files\FocusLock\FocusLock.exe"


# ---------- hosts ----------

def test_hosts_add_and_remove_block_round_trip():
    original = "127.0.0.1 localhost\r\n# a comment\r\n"
    blocked = win.hosts_add_block(original, ["poki.com"])
    assert "0.0.0.0 poki.com\r\n" in blocked and ":: poki.com\r\n" in blocked
    assert win.hosts_add_block(blocked, ["other.com"]) == blocked   # never twice
    assert win.hosts_remove_block(blocked) == original


def test_hosts_add_block_without_trailing_newline():
    blocked = win.hosts_add_block("127.0.0.1 localhost", ["poki.com"])
    assert blocked.startswith("127.0.0.1 localhost\n# FOCUSLOCK-START")


def test_hosts_youtube_break_round_trip():
    text = win.hosts_add_block("", ["poki.com", *win.YT_DOMAINS])
    during = win.hosts_remove_domains(text, win.YT_DOMAINS)
    assert "youtube" not in during and "0.0.0.0 poki.com" in during
    after = win.hosts_add_domains(during, win.YT_DOMAINS)
    assert sorted(after.splitlines()) == sorted(text.splitlines())


def test_no_block_for_no_domains():
    assert win.hosts_add_block("x\n", []) == "x\n"


# ---------- tasks and matching ----------

def test_task_xml_is_valid():
    xml = win.task_xml("desc & more", EXE, "--unlock", at="2030-01-04 10:00:00", boot=True)
    root = ET.fromstring(xml.replace('encoding="UTF-16"', ""))
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert root.find(".//t:TimeTrigger/t:StartBoundary", ns).text == "2030-01-04T10:00:00"
    assert root.find(".//t:BootTrigger", ns) is not None
    assert root.find(".//t:UserId", ns).text == "S-1-5-18"
    assert root.find(".//t:Command", ns).text == EXE
    forever = ET.fromstring(win.task_xml("g", EXE, "--guard", boot=True, forever=True)
                            .replace('encoding="UTF-16"', ""))
    assert forever.find(".//t:ExecutionTimeLimit", ns).text == "PT0S"


def test_match_blocked():
    guard = {"godot": ["Godot*.exe"], "steam": ["steam.exe"]}
    assert win.match_blocked("Godot_v4.3-stable_win64.exe", guard) == "godot"
    assert win.match_blocked("STEAM.EXE", guard) == "steam"
    assert win.match_blocked("steamwebhelper.exe", guard) is None


def test_debugger_command_quotes_the_path():
    assert win.debugger_command(EXE, "steam") == f'"{EXE}" --blocked steam'


# ---------- what gets blocked ----------

def test_plan_lock_validates_custom_entries(monkeypatch):
    monkeypatch.setattr(core, "check_custom_path",
                        lambda p: None if p.endswith("ok.exe") else "nope")
    defs = "\n".join(["c_game\tGame\tpath\tC:\\Users\\me\\Games\\ok.exe",
                      "c_bad\tBad\tpath\tC:\\Windows\\explorer.exe",
                      "evil\tX\tpath\tC:\\Users\\me\\ok.exe",          # invalid key
                      "c_fp\tFP\tflatpak\torg.example.App"])           # no Flatpak on Windows
    sites = "w_reddit\tReddit\treddit.com www.reddit.com\nw_bad\tBad\tlocalhost"
    apps, guard, domain_keys, domains = win.plan_lock("steam,c_game,c_bad,evil,c_fp",
                                                      "poki,w_reddit,w_bad", defs, sites)
    assert apps == ["steam", "c_game"]
    assert guard == {"steam": ["steam.exe"], "c_game": ["ok.exe"]}
    assert domain_keys == ["poki", "w_reddit"]
    assert domains == ["poki.com", "www.poki.com", "reddit.com", "www.reddit.com"]


def test_plan_lock_none():
    assert win.plan_lock("none", "none", "", "") == ([], {}, [], [])


# ---------- the steps, against a fake system ----------

class FakeSystem:
    def __init__(self, tmp_path, monkeypatch):
        self.now = 1_900_000_000.0
        self.tasks, self.ifeo, self.commands = {}, {}, []
        self.lockdir = tmp_path / "ProgramData" / "FocusLock"
        self.hosts = tmp_path / "hosts"
        self.hosts.write_text("127.0.0.1 localhost\r\n", newline="")
        monkeypatch.setattr(win, "LOCKDIR", str(self.lockdir))
        monkeypatch.setattr(win, "HOSTS", str(self.hosts))
        monkeypatch.setattr(win, "_now", lambda: self.now)
        monkeypatch.setattr(win, "require_installed", lambda: EXE)
        monkeypatch.setattr(win, "lock_dirs", lambda: os.makedirs(self.lockdir, exist_ok=True))
        monkeypatch.setattr(win, "_run", lambda cmd: self.commands.append(cmd))
        monkeypatch.setattr(win, "create_task", self.create_task)
        monkeypatch.setattr(win, "delete_task", lambda name: self.tasks.pop(name, None))
        monkeypatch.setattr(win, "ifeo_block", self.ifeo_block)
        monkeypatch.setattr(win, "ifeo_restore", lambda r: self.ifeo.pop(r["name"], None))
        monkeypatch.setattr(win, "ifeo_sweep", lambda: None)
        self.fail_task = None

    def create_task(self, name, xml):
        if name == self.fail_task:
            raise win.LockError("task failed")
        self.tasks[name] = xml

    def ifeo_block(self, name, command):
        if self.ifeo.get(name) == command:
            return []
        self.ifeo[name] = command
        return [{"name": name, "view": 0, "existed": False, "old": None}]

    def stamp(self, seconds):
        from datetime import datetime
        return datetime.fromtimestamp(self.now + seconds).strftime("%Y-%m-%d %H:%M:%S")

    def apply(self, seconds=3600, apps="steam,godot", domains="poki,youtube"):
        cal = self.stamp(seconds)
        win.apply([f"Someday, {cal} UTC", cal, apps, domains, "write the essay", "", ""])


@pytest.fixture
def system(tmp_path, monkeypatch):
    return FakeSystem(tmp_path, monkeypatch)


def test_apply_blocks_everything(system):
    system.apply()
    lock = system.lockdir
    assert (lock / "selected_apps").read_text().split() == ["steam", "godot"]
    assert (lock / "selected_domains").read_text().split() == ["poki", "youtube"]
    assert (lock / "intent").read_text().strip() == "write the essay"
    assert json.loads((lock / "guard.json").read_text()) == {"steam": ["steam.exe"], "godot": ["Godot*.exe"]}
    assert "0.0.0.0 poki.com" in system.hosts.read_text()
    assert system.ifeo == {"steam.exe": f'"{EXE}" --blocked steam'}   # no registry key for a * name
    assert set(system.tasks) == {win.TASK_UNLOCK, win.TASK_GUARD}
    assert ["schtasks", "/Run", "/TN", win.TASK_GUARD] in system.commands


def test_apply_refuses_a_second_lock_and_past_times(system):
    system.apply()
    with pytest.raises(win.LockError, match="already active"):
        system.apply()
    win.unlock(force=True)
    with pytest.raises(win.LockError, match="past"):
        system.apply(seconds=-60)


def test_failed_apply_leaves_nothing_behind(system):
    system.fail_task = win.TASK_GUARD
    with pytest.raises(win.LockError):
        system.apply()
    assert not system.lockdir.exists()
    assert system.hosts.read_bytes() == b"127.0.0.1 localhost\r\n"
    assert system.ifeo == {} and system.tasks == {}


def test_unlock_does_nothing_early_then_cleans_up(system):
    system.apply(seconds=3600)
    assert win.unlock() is False                       # e.g. the boot trigger
    assert system.lockdir.exists() and system.ifeo
    system.now += 3601
    assert win.unlock() is True
    assert not system.lockdir.exists()
    assert system.hosts.read_bytes() == b"127.0.0.1 localhost\r\n"
    assert system.ifeo == {} and system.tasks == {}


def test_youtube_break(system):
    system.apply()
    reblock = system.stamp(3600)
    win.youtube_break([f"Someday, {reblock}", reblock])
    assert "youtube" not in system.hosts.read_text()
    assert win.TASK_REBLOCK in system.tasks
    assert (system.lockdir / "youtube_break_last_used").read_text().strip() == date.today().isoformat()
    with pytest.raises(win.LockError, match="already been used"):
        win.youtube_break([f"Someday, {reblock}", reblock])
    win.reblock()
    assert "0.0.0.0 www.youtube.com" in system.hosts.read_text()
    assert win.TASK_REBLOCK not in system.tasks


def test_repair_puts_removed_blocks_back(system):
    system.apply()
    system.hosts.write_text("127.0.0.1 localhost\r\n", newline="")
    system.ifeo.clear()
    win.repair(EXE, json.loads((system.lockdir / "guard.json").read_text()))
    assert "0.0.0.0 poki.com" in system.hosts.read_text()
    assert "steam.exe" in system.ifeo


def test_run_with_args_file_reports_errors(system, tmp_path):
    args = tmp_path / "args.json"
    args.write_text(json.dumps(["x", "not a time"]))
    assert win.run_with_args_file(win.apply, str(args)) == 1
    assert "past" in (tmp_path / "args.json.err").read_text()
    args.write_text('{"not": "a list"}')
    assert win.run_with_args_file(win.apply, str(args)) == 1
