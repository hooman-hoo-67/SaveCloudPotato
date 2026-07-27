"""
Tests for the command-line interface.

Commands are thin by design, so these check the wiring and the user
facing behaviour rather than re-testing service logic.
"""

from __future__ import annotations

from typer.testing import CliRunner

from savecloud.cli import app
from savecloud.services.configuration import ConfigurationService
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, read_save, write_save
from tests.test_sync import advance_remote

runner = CliRunner()


def invoke(*arguments):
    """
    Run the CLI with the given arguments.
    """

    return runner.invoke(app, list(arguments))


#
# Wiring
#


def test_help_lists_every_command():

    result = invoke("--help")

    assert result.exit_code == 0

    for command in (
        "init",
        "register",
        "list",
        "info",
        "unregister",
        "import",
        "export",
        "snapshot",
        "history",
        "restore",
        "upload",
        "download",
        "sync",
        "play",
        "pair",
        "config",
    ):
        assert command in result.output


#
# init
#


def test_init_creates_the_installation(monkeypatch, tmp_path):

    monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / "fresh"))

    result = invoke("init")

    assert result.exit_code == 0

    assert (tmp_path / "fresh" / "config.json").exists()
    assert (tmp_path / "fresh" / "library").is_dir()
    assert (tmp_path / "fresh" / "registry").is_dir()


def test_init_is_idempotent():

    result = invoke("init")

    assert result.exit_code == 0
    assert "already initialized" in result.output


def test_init_adopts_a_legacy_storage_backend(monkeypatch, tmp_path):
    """
    Upgrading an installation that configured storage per game.
    """

    import json

    home = tmp_path / "legacy"

    monkeypatch.setenv("SAVECLOUD_HOME", str(home))

    invoke("init")

    #
    # Write a pre-Milestone-8 manifest, then remove the config so init
    # runs its migration path.
    #

    from tests.conftest import build_game

    RegistryService.create_registry(build_game())

    path = RegistryService.registry_manifest_path(GAME_ID)

    data = json.loads(path.read_text(encoding="utf-8"))

    data["storage_backend"] = "syncthing"

    path.write_text(json.dumps(data), encoding="utf-8")

    ConfigurationService.path().unlink()

    result = invoke("init")

    assert result.exit_code == 0
    assert ConfigurationService.load().storage_backend == "syncthing"


#
# config
#


def test_config_show(storage_root):

    result = invoke("config", "show")

    assert result.exit_code == 0
    assert "local" in result.output
    assert str(storage_root) in result.output


def test_config_backend_lists_available_backends():

    result = invoke("config", "backend")

    assert result.exit_code == 0
    assert "local" in result.output
    assert "syncthing" in result.output


def test_config_backend_changes_the_backend():

    result = invoke("config", "backend", "syncthing")

    assert result.exit_code == 0
    assert ConfigurationService.load().storage_backend == "syncthing"


def test_config_backend_rejects_an_unknown_backend():

    result = invoke("config", "backend", "dropbox")

    assert result.exit_code == 1
    assert "Unknown storage backend" in result.output

    assert ConfigurationService.load().storage_backend == "local"


def test_config_root_changes_the_root(tmp_path):

    result = invoke("config", "root", str(tmp_path / "moved"))

    assert result.exit_code == 0
    assert ConfigurationService.load().storage_root == tmp_path / "moved"


def test_config_validate_passes_for_local():

    result = invoke("config", "validate")

    assert result.exit_code == 0
    assert "available" in result.output


def test_config_validate_fails_for_an_unusable_backend():

    ConfigurationService.set_backend("syncthing")

    result = invoke("config", "validate")

    assert result.exit_code == 1


#
# Game commands
#


def test_list_reports_an_empty_registry():

    result = invoke("list")

    assert result.exit_code == 0
    assert "No games" in result.output


def test_list_shows_registered_games(registered_game):

    result = invoke("list")

    assert result.exit_code == 0
    assert GAME_ID in result.output


def test_info_shows_installation_storage(registered_game):

    result = invoke("info", GAME_ID)

    assert result.exit_code == 0
    assert "installation-wide" in result.output
    assert GAME_ID in result.output


def test_info_rejects_an_unregistered_game():

    result = invoke("info", "nonexistent")

    assert result.exit_code == 1
    assert "not registered" in result.output


def test_snapshot_and_history(registered_game):

    assert invoke("import", GAME_ID).exit_code == 0

    assert invoke("snapshot", GAME_ID).exit_code == 0

    result = invoke("history", GAME_ID)

    assert result.exit_code == 0
    assert "1" in result.output


def test_restore(registered_game, working_save):

    invoke("import", GAME_ID)
    invoke("snapshot", GAME_ID)

    write_save(working_save, "later")

    invoke("import", GAME_ID)

    result = invoke("restore", GAME_ID, "1")

    assert result.exit_code == 0

    assert invoke("export", GAME_ID).exit_code == 0

    assert read_save(working_save) == "original"


#
# sync
#


def test_sync_uploads(registered_game):

    result = invoke("sync", GAME_ID)

    assert result.exit_code == 0
    assert "Uploaded" in result.output

    assert LocalStorageBackend.exists(GAME_ID)


def test_sync_reports_up_to_date(registered_game):

    invoke("sync", GAME_ID)

    result = invoke("sync", GAME_ID)

    assert result.exit_code == 0
    assert "up to date" in result.output


def test_sync_check_changes_nothing(registered_game, working_save):

    invoke("sync", GAME_ID)

    write_save(working_save, "changed")

    result = invoke("sync", GAME_ID, "--check")

    assert result.exit_code == 0
    assert "upload" in result.output

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


def test_sync_reports_a_conflict_with_guidance(registered_game, working_save):

    invoke("sync", GAME_ID)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    result = invoke("sync", GAME_ID)

    assert result.exit_code == 1
    assert "--keep-local" in result.output
    assert "--keep-remote" in result.output

    #
    # Nothing was overwritten.
    #

    assert read_save(working_save) == "local progress"


def test_sync_keep_local_resolves(registered_game, working_save):

    invoke("sync", GAME_ID)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    result = invoke("sync", GAME_ID, "--keep-local")

    assert result.exit_code == 0

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "local progress"


def test_sync_rejects_contradictory_flags(registered_game):

    result = invoke("sync", GAME_ID, "--keep-local", "--keep-remote")

    assert result.exit_code == 2


def test_sync_rejects_an_unregistered_game():

    result = invoke("sync", "nonexistent")

    assert result.exit_code == 1
    assert "not registered" in result.output


def test_sync_without_a_game_covers_everything(registered_game):

    result = invoke("sync")

    assert result.exit_code == 0
    assert "Synchronized 1 games" in result.output


def test_sync_reports_unavailable_storage(registered_game):

    ConfigurationService.set_backend("syncthing")

    result = invoke("sync", GAME_ID)

    assert result.exit_code == 1
    assert "Syncthing" in result.output


#
# play
#


def test_play_runs_the_full_workflow(tmp_path):

    from tests.conftest import register_game

    working = tmp_path / "working"

    write_save(working, "before")

    register_game(
        working,
        launch_command=f"sh -c \"printf 'after' > {working / 'save.dat'}\"",
    )

    result = invoke("play", GAME_ID)

    assert result.exit_code == 0
    assert "uploaded" in result.output

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "after"


def test_play_reports_a_crash(tmp_path):

    from tests.conftest import register_game

    working = tmp_path / "working"

    write_save(working, "before")

    register_game(working, launch_command="false")

    result = invoke("play", GAME_ID)

    assert result.exit_code == 1
    assert "exited with code 1" in result.output


def test_play_rejects_an_unregistered_game():

    result = invoke("play", "nonexistent")

    assert result.exit_code == 1
    assert "not registered" in result.output


#
# pair
#


def test_pair_list_reports_an_empty_backend():

    result = invoke("pair", "--list")

    assert result.exit_code == 0
    assert "no games" in result.output.lower()


def test_pair_list_shows_uploaded_games(registered_game):

    SyncService.sync(registered_game)

    result = invoke("pair", "--list")

    assert result.exit_code == 0
    assert GAME_ID in result.output
    assert "paired" in result.output


def test_pair_rejects_an_unknown_game(registered_game):

    SyncService.sync(registered_game)

    result = invoke("pair", "nonexistent")

    assert result.exit_code == 1


def test_pair_refuses_to_re_pair(registered_game):

    SyncService.sync(registered_game)

    result = invoke("pair", GAME_ID)

    assert result.exit_code == 1
    assert "already paired" in result.output


#
# unregister
#


def test_unregister_removes_a_game(registered_game):

    result = runner.invoke(app, ["unregister", GAME_ID], input="y\n")

    assert result.exit_code == 0
    assert not RegistryService.exists(GAME_ID)


def test_unregister_can_be_cancelled(registered_game):

    result = runner.invoke(app, ["unregister", GAME_ID], input="n\n")

    assert result.exit_code == 0
    assert RegistryService.exists(GAME_ID)
