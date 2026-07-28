"""
Tests for Steam integration.

Steam is not installed in the test environment, so these build the
directory layouts Steam produces and point discovery at them through
SAVECLOUD_STEAM_ROOT.
"""

from __future__ import annotations

import pytest

from savecloud.adapters import AdapterRegistry
from savecloud.adapters.steam_proton import SteamProtonAdapter
from savecloud.launchers import LauncherRegistry, SteamLauncher
from savecloud.utils import steam, vdf

APP_ID = "2050650"


#
# VDF
#


def test_vdf_reads_nested_blocks():

    data = vdf.loads(
        """
        "libraryfolders"
        {
            "0"
            {
                "path"      "/home/user/.local/share/Steam"
                "label"     ""
            }
        }
        """
    )

    assert data["libraryfolders"]["0"]["path"] == (
        "/home/user/.local/share/Steam"
    )


def test_vdf_ignores_comments():

    data = vdf.loads(
        """
        // a comment
        "AppState"
        {
            "appid"  "220"   // trailing comment
            "name"   "Half-Life 2"
        }
        """
    )

    assert data["AppState"]["name"] == "Half-Life 2"


def test_vdf_resolves_escapes():

    data = vdf.loads(r'"k" { "path" "C:\\Games\\My Game" }')

    assert data["k"]["path"] == r"C:\Games\My Game"


def test_vdf_tolerates_truncation():
    """
    Steam writes these files; a partial read must not crash SaveCloud.
    """

    data = vdf.loads('"libraryfolders" { "0" { "path" "/games"')

    assert data["libraryfolders"]["0"]["path"] == "/games"


def test_vdf_of_a_missing_file_is_empty(tmp_path):

    assert vdf.load(tmp_path / "absent.vdf") == {}


#
# Steam discovery
#


@pytest.fixture
def steam_install(tmp_path, monkeypatch):
    """
    Build a Steam installation with one library and one Proton game.
    """

    root = tmp_path / "Steam"

    steamapps = root / "steamapps"

    steamapps.mkdir(parents=True)

    (steamapps / "libraryfolders.vdf").write_text(
        f"""
        "libraryfolders"
        {{
            "0"
            {{
                "path"  "{root}"
            }}
        }}
        """,
        encoding="utf-8",
    )

    (steamapps / f"appmanifest_{APP_ID}.acf").write_text(
        f"""
        "AppState"
        {{
            "appid"  "{APP_ID}"
            "name"   "Test Proton Game"
        }}
        """,
        encoding="utf-8",
    )

    user = (
        steamapps
        / "compatdata"
        / APP_ID
        / "pfx"
        / "drive_c"
        / "users"
        / "steamuser"
    )

    (user / "AppData" / "Roaming" / "TestGame").mkdir(parents=True)
    (user / "Documents" / "My Games" / "TestGame").mkdir(parents=True)

    monkeypatch.setenv(steam.STEAM_ROOT_ENV, str(root))

    return root


def test_steam_root_is_found(steam_install):

    assert steam.steam_root() == steam_install


def test_steam_root_is_none_when_absent(monkeypatch, tmp_path):

    monkeypatch.setenv(steam.STEAM_ROOT_ENV, str(tmp_path / "absent"))

    assert steam.steam_root() is None


def test_libraries_include_the_root(steam_install):

    assert steam_install in steam.library_folders()


def test_extra_libraries_are_discovered(steam_install, tmp_path):
    """
    A second drive or SD card is recorded in libraryfolders.vdf.
    """

    second = tmp_path / "SDCard"

    (second / "steamapps").mkdir(parents=True)

    (steam_install / "steamapps" / "libraryfolders.vdf").write_text(
        f"""
        "libraryfolders"
        {{
            "0" {{ "path" "{steam_install}" }}
            "1" {{ "path" "{second}" }}
        }}
        """,
        encoding="utf-8",
    )

    libraries = steam.library_folders()

    assert steam_install in libraries
    assert second in libraries


def test_a_library_listed_but_missing_is_skipped(steam_install, tmp_path):

    (steam_install / "steamapps" / "libraryfolders.vdf").write_text(
        f"""
        "libraryfolders"
        {{
            "0" {{ "path" "{steam_install}" }}
            "1" {{ "path" "{tmp_path / 'unplugged'}" }}
        }}
        """,
        encoding="utf-8",
    )

    assert steam.library_folders() == [steam_install]


def test_installed_apps_are_read(steam_install):

    assert steam.installed_apps() == {APP_ID: "Test Proton Game"}


def test_app_name(steam_install):

    assert steam.app_name(APP_ID) == "Test Proton Game"
    assert steam.app_name("999999") is None


def test_compat_prefix_is_found(steam_install):

    prefix = steam.compat_prefix(APP_ID)

    assert prefix is not None
    assert prefix.name == "pfx"


def test_compat_prefix_is_none_for_an_unplayed_game(steam_install):
    """
    Proton creates the prefix on first run, not on install.
    """

    assert steam.compat_prefix("999999") is None


def test_prefix_user_directory(steam_install):

    user = steam.prefix_user_directory(APP_ID)

    assert user is not None
    assert user.name == "steamuser"


def test_prefix_falls_back_to_a_single_named_user(steam_install, tmp_path):
    """
    Older prefixes used the host account name instead of steamuser.
    """

    users = (
        steam_install
        / "steamapps"
        / "compatdata"
        / APP_ID
        / "pfx"
        / "drive_c"
        / "users"
    )

    (users / "steamuser").rename(users / "hooman")

    user = steam.prefix_user_directory(APP_ID)

    assert user is not None
    assert user.name == "hooman"


def test_candidate_save_directories(steam_install):

    candidates = steam.candidate_save_directories(APP_ID)

    names = [path.name for path in candidates]

    assert "TestGame" in names

    #
    # Both AppData/Roaming and Documents/My Games held one.
    #

    assert len(candidates) == 2


def test_candidates_are_empty_without_a_prefix(steam_install):

    assert steam.candidate_save_directories("999999") == []


#
# Proton adapter
#


def test_the_adapter_is_registered():

    assert AdapterRegistry.get("steam-proton") is SteamProtonAdapter


def test_adapter_locates_the_user_directory_from_an_app_id(steam_install):

    located = SteamProtonAdapter.locate_save(APP_ID)

    assert located is not None
    assert located.name == "steamuser"


def test_adapter_locates_a_specific_save_directory(steam_install):
    """
    Registration records the chosen subdirectory alongside the App ID.
    """

    located = SteamProtonAdapter.locate_save(
        f"{APP_ID}:AppData/Roaming/TestGame",
    )

    assert located is not None
    assert located.name == "TestGame"
    assert located.parent.name == "Roaming"


def test_adapter_rejects_a_missing_subdirectory(steam_install):

    assert SteamProtonAdapter.locate_save(f"{APP_ID}:AppData/Roaming/Absent") is None


def test_adapter_rejects_an_unplayed_game(steam_install):

    assert SteamProtonAdapter.locate_save("999999") is None


def test_adapter_rejects_an_empty_identifier(steam_install):

    assert SteamProtonAdapter.locate_save("") is None
    assert SteamProtonAdapter.locate_save(":some/path") is None


def test_adapter_validates_directories(steam_install, tmp_path):

    assert SteamProtonAdapter.validate_save(steam_install)
    assert not SteamProtonAdapter.validate_save(tmp_path / "absent")


#
# Steam launcher
#


def test_the_launcher_is_registered():

    assert LauncherRegistry.get("steam") is SteamLauncher


def test_the_launcher_cannot_track_process_exit():
    """
    The reason `play` refuses it and `wrap` exists.
    """

    assert not SteamLauncher.tracks_process_exit()


def test_other_launchers_do_track_exit():

    from savecloud.launchers import AppImageLauncher, NativeLauncher

    assert NativeLauncher.tracks_process_exit()
    assert AppImageLauncher.tracks_process_exit()


def test_launcher_rejects_an_empty_command():

    assert not SteamLauncher.validate("")
    assert not SteamLauncher.validate("   ")


def test_launcher_accepts_an_app_id_when_steam_is_present(monkeypatch):

    monkeypatch.setattr(
        "savecloud.launchers.steam.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )

    assert SteamLauncher.validate(APP_ID)


def test_launcher_rejects_an_app_id_without_steam(monkeypatch):

    monkeypatch.setattr(
        "savecloud.launchers.steam.shutil.which",
        lambda name: None,
    )

    assert not SteamLauncher.validate(APP_ID)
