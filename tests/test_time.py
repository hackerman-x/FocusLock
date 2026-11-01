import time

import focuslock_core as core


def test_offset_seconds():
    assert core.offset_seconds("+2 days +3 hours +5 minutes") == 2 * 86400 + 3 * 3600 + 5 * 60
    assert core.offset_seconds("+1 hour") == 3600
    assert core.offset_seconds(None) == 0


def test_run_date_round_trips_through_parse():
    human = core.run_date("+%A, %Y-%m-%d %H:%M:%S %Z", offset="+1 hour")
    assert abs(core.parse_unlock_time(human) - (time.time() + 3600)) < 3
    calendar = core.run_date("+%Y-%m-%d %H:%M:%S", offset="+2 days")
    assert abs(core.parse_unlock_time(calendar) - (time.time() + 2 * 86400)) < 3


def test_parse_unlock_time_accepts_long_windows_zone_names():
    a = core.parse_unlock_time("Tuesday, 2026-11-03 12:00:00 India Standard Time")
    b = core.parse_unlock_time("Tuesday, 2026-11-03 12:00:00 IST")
    assert a == b is not None


def test_parse_unlock_time_rejects_garbage():
    assert core.parse_unlock_time("soon") is None
    assert core.parse_unlock_time(None) is None


def test_lock_progress(tmp_path, monkeypatch):
    started, unlock_at = tmp_path / "locked_at", tmp_path / "unlock_at"
    monkeypatch.setattr(core, "LOCKED_AT_FILE", str(started))
    monkeypatch.setattr(core, "UNLOCK_AT_FILE", str(unlock_at))
    assert core.lock_progress() is None
    started.write_text("1700000000\n")
    unlock_at.write_text("Friday, 2030-01-04 10:00:00 UTC\n")
    s, e = core.lock_progress()
    assert s == 1700000000 and e == core.parse_unlock_time("2030-01-04 10:00:00")
