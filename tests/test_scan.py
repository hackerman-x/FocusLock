import pytest

import focuslock_core as core
import focuslock_scan as scan


@pytest.mark.parametrize("names, expected", [
    (("Epic Games Launcher", "EpicGamesLauncher"), scan.GAME),
    (("GOG GALAXY", "GalaxyClient"), scan.GAME),
    (("Battle.net", "Battle.net Launcher"), scan.GAME),
    (("EA", "EADesktop"), scan.GAME),
    (("Ubisoft Connect", "UbisoftConnect"), scan.GAME),
    (("League of Legends", "LeagueClient"), scan.GAME),
    (("Riot Client", "RiotClientServices"), scan.GAME),
    (("Prime Video", "PrimeVideo"), scan.MEDIA),
    (("JioHotstar", "hotstar"), scan.MEDIA),
    (("Spotify", "Spotify"), scan.MEDIA),
    (("Visual Studio Code", "Code"), None),
    (("Blender", "blender"), None),
    (("Teardown", "teardown"), None),        # "ea" must not match inside a word
])
def test_known_category(names, expected):
    assert scan._known_category(*names) == expected


def test_windows_scan_suggests_launchers_only(monkeypatch, tmp_path):
    shortcuts = [
        ("Epic Games Launcher", r"C:\Program Files (x86)\Epic Games\Launcher\EpicGamesLauncher.exe"),
        ("Riot Client", r"C:\Riot Games\Riot Client\RiotClientServices.exe"),
        ("Visual Studio Code", r"C:\Users\me\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
        ("Steam", r"C:\Program Files (x86)\Steam\steam.exe"),       # a built-in app already
        ("Uninstall Spotify", r"C:\Users\me\AppData\Roaming\Spotify\unins000.exe"),
        ("Spotify Updater", r"C:\Users\me\AppData\Roaming\Spotify\Update.exe"),
        ("Spotify", r"C:\Users\me\AppData\Roaming\Spotify\Spotify.exe"),
    ]
    monkeypatch.setattr(scan, "_start_menu_shortcuts", lambda: shortcuts)
    monkeypatch.setattr(scan, "check_custom_path", lambda path: None)
    monkeypatch.setattr(scan, "load_custom_apps", lambda: [])
    monkeypatch.setattr(scan, "_steam_library_games", lambda: set())
    monkeypatch.setattr(scan, "BUILTIN_NAMES",
                        set().union(*(core.win_exe_names(v) for v in core.WIN_APP_EXES.values())))
    result = scan._scan_windows(set(), str(tmp_path))
    names = [r["name"] for r in result["recommendations"]]
    assert names == ["Epic Games Launcher", "Riot Client", "Spotify"]
    assert all(r["source"] == "path" for r in result["recommendations"])
    ignored = {result["recommendations"][0]["id"]}
    again = scan._scan_windows(ignored, str(tmp_path))
    assert "Epic Games Launcher" not in [r["name"] for r in again["recommendations"]]
