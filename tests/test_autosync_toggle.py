"""
Tests for per-device automatic synchronization.

Two switches, deliberately. `sync_enabled` on the manifest travels with
the game; `enabled` on the device profile stays put. The second is what
lets one device stop uploading without changing anything for the others
it shares saves with.
"""

from __future__ import annotations

from typer.testing import CliRunner

from savecloud.cli import app
from savecloud.services.autosync import AutoSyncService, auto_sync_enabled
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, read_save, register_game, write_save

runner = CliRunner()


def disable_here(game_id: str = GAME_ID) -> None:
    """
    Opt this device out of automatic sync for a game.
    """

    profile = DeviceService.load_profile(SaveCloudLibrary.device_id(), game_id)

    profile.enabled = False

    DeviceService.save_profile(profile)


#
# The rule
#


def test_a_game_is_automatic_by_default(registered_game):

    assert auto_sync_enabled(registered_game) is True


def test_a_disabled_device_opts_out(registered_game):

    disable_here()

    assert auto_sync_enabled(RegistryService.load_game(GAME_ID)) is False


def test_a_disabled_game_overrides_an_enabled_device(tmp_path):
    """
    The manifest switch means "managed at all", so it wins.
    """

    working = tmp_path / "working"

    write_save(working, "contents")

    game = register_game(working, sync_enabled=False)

    assert auto_sync_enabled(game) is False


def test_a_game_without_a_profile_here_follows_the_manifest(registered_game):
    """
    A device with no profile has nothing to say about the game.
    """

    DeviceService.delete_profile(SaveCloudLibrary.device_id(), GAME_ID)

    assert auto_sync_enabled(RegistryService.load_game(GAME_ID)) is True


#
# What it actually gates
#


def test_playing_does_not_upload_when_disabled(tmp_path):

    working = tmp_path / "working"

    write_save(working, "original")

    register_game(working, launch_command="true")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    disable_here()

    write_save(working, "played offline by choice")

    result = AutoSyncService.play(RegistryService.load_game(GAME_ID))

    assert result.uploaded is False

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


def test_sync_all_skips_a_disabled_game(registered_game, working_save):

    disable_here()

    write_save(working_save, "progress")

    assert SyncService.sync_all() == {}


def test_naming_the_game_still_synchronizes_it(registered_game, working_save):
    """
    The switch governs automatic behaviour, not explicit commands.
    """

    disable_here()

    write_save(working_save, "asked for explicitly")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert read_save(
        LocalStorageBackend.current_directory(GAME_ID)
    ) == "asked for explicitly"


#
# CLI
#


def test_cli_shows_the_current_setting(registered_game):

    result = runner.invoke(app, ["autosync", GAME_ID])

    assert result.exit_code == 0

    assert "on" in result.output


def test_cli_turns_it_off_and_on(registered_game):

    assert runner.invoke(app, ["autosync", GAME_ID, "off"]).exit_code == 0

    assert auto_sync_enabled(RegistryService.load_game(GAME_ID)) is False

    assert runner.invoke(app, ["autosync", GAME_ID, "on"]).exit_code == 0

    assert auto_sync_enabled(RegistryService.load_game(GAME_ID)) is True


def test_cli_rejects_anything_other_than_on_or_off(registered_game):

    result = runner.invoke(app, ["autosync", GAME_ID, "maybe"])

    assert result.exit_code == 1

    assert auto_sync_enabled(RegistryService.load_game(GAME_ID)) is True


def test_cli_says_when_the_game_itself_is_disabled(tmp_path):

    working = tmp_path / "working"

    write_save(working, "contents")

    register_game(working, sync_enabled=False)

    result = runner.invoke(app, ["autosync", GAME_ID])

    assert "every device" in result.output


def test_cli_emits_json(registered_game):

    import json

    result = runner.invoke(app, ["--json", "autosync", GAME_ID, "off"])

    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["auto_sync"] is False
    assert payload["device"] is False
    assert payload["game"] is True


def test_the_setting_is_not_synchronized(registered_game, working_save):
    """
    It lives in the device profile, which never travels.
    """

    disable_here()

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    remote = LocalStorageBackend.game_directory(GAME_ID)

    assert not (remote / "profile.json").exists()

    for path in remote.rglob("*.json"):
        assert "enabled" not in path.read_text() or path.name != "profile.json"
