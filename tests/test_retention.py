"""
Tests for version retention.

Every synchronization that finds a change creates a version, so without
a limit the history grows forever - and on a cloud backend, every one
of those versions is uploaded.
"""

from __future__ import annotations

from typer.testing import CliRunner

from savecloud.cli import app
from savecloud.models.installation_config import InstallationConfig
from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import SyncService
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, read_save, write_save

runner = CliRunner()


def play_sessions(game, working_save, count: int) -> None:
    """
    Simulate several play-and-sync cycles.
    """

    for index in range(count):

        write_save(working_save, f"session {index}")

        SyncService.sync(RegistryService.load_game(GAME_ID))


#
# Local library
#


def test_only_the_configured_number_of_versions_survives(
    registered_game,
    working_save,
):

    play_sessions(registered_game, working_save, 6)

    versions = SaveService.list_versions(RegistryService.load_game(GAME_ID))

    assert len(versions) == 2


def test_the_newest_versions_are_the_ones_kept(registered_game, working_save):

    play_sessions(registered_game, working_save, 5)

    game = RegistryService.load_game(GAME_ID)

    versions = SaveService.list_versions(game)

    #
    # The survivors must be the most recent, not an arbitrary two.
    #

    assert versions == sorted(versions)[-2:]

    newest = read_save(SaveCloudLibrary.version_directory(GAME_ID, versions[-1]))

    assert newest == "session 4"


def test_the_current_save_is_not_a_version(registered_game, working_save):
    """
    Retention counts history only, so keep=2 leaves three saves total.
    """

    play_sessions(registered_game, working_save, 5)

    game = RegistryService.load_game(GAME_ID)

    assert len(SaveService.list_versions(game)) == 2

    assert read_save(SaveService.current_save(game)) == "session 4"


def test_retention_can_be_raised(registered_game, working_save):

    ConfigurationService.set_retention(4)

    play_sessions(registered_game, working_save, 8)

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 4


def test_zero_keeps_everything(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 6)

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) >= 6


def test_lowering_retention_trims_on_the_next_capture(
    registered_game,
    working_save,
):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 5)

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) >= 5

    ConfigurationService.set_retention(1)

    play_sessions(registered_game, working_save, 1)

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 1


def test_restore_still_works_within_the_window(registered_game, working_save):
    """
    Retention must not break the feature history exists for.
    """

    play_sessions(registered_game, working_save, 3)

    game = RegistryService.load_game(GAME_ID)

    versions = SaveService.list_versions(game)

    oldest_kept = versions[0]

    contents = read_save(SaveCloudLibrary.version_directory(GAME_ID, oldest_kept))

    SaveService.restore_version(game, oldest_kept)

    assert read_save(SaveService.current_save(game)) == contents


def test_pruning_reports_what_it_removed(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 4)

    removed = SaveCloudLibrary.prune_versions(GAME_ID, 1)

    assert len(removed) >= 2

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 1


def test_pruning_a_game_without_versions_is_harmless():

    assert SaveCloudLibrary.prune_versions("no-such-game", 2) == []


#
# Storage
#


def test_storage_keeps_only_the_retained_versions(registered_game, working_save):

    play_sessions(registered_game, working_save, 6)

    remote = LocalStorageBackend.versions_directory(GAME_ID)

    names = sorted(path.name for path in remote.iterdir() if path.is_dir())

    assert len(names) == 2


def test_storage_and_library_agree_on_which_versions_survive(
    registered_game,
    working_save,
):

    play_sessions(registered_game, working_save, 5)

    game = RegistryService.load_game(GAME_ID)

    local = {f"{version:06d}" for version in SaveService.list_versions(game)}

    remote = LocalStorageBackend.versions_directory(GAME_ID)

    stored = {path.name for path in remote.iterdir() if path.is_dir()}

    assert local == stored


def test_a_pruned_version_is_not_re_uploaded(registered_game, working_save):
    """
    A device still holding old history must not keep restoring what
    another device pruned, or the two would never agree.
    """

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 4)

    remote = LocalStorageBackend.versions_directory(GAME_ID)

    assert len({path.name for path in remote.iterdir() if path.is_dir()}) >= 4

    #
    # Tighten retention and sync once more.
    #

    ConfigurationService.set_retention(1)

    play_sessions(registered_game, working_save, 1)

    stored = {path.name for path in remote.iterdir() if path.is_dir()}

    assert len(stored) == 1


def test_storage_retention_of_zero_keeps_everything(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 5)

    remote = LocalStorageBackend.versions_directory(GAME_ID)

    assert len({path.name for path in remote.iterdir() if path.is_dir()}) >= 5


#
# Dropbox
#


def test_dropbox_prunes_remote_versions(monkeypatch, tmp_path, working_save):

    from savecloud.services.credentials import CredentialService
    from savecloud.storage.dropbox import PROVIDER, DropboxStorageBackend
    from tests.conftest import register_game
    from tests.fake_dropbox import FakeDropbox

    fake = FakeDropbox().install(monkeypatch)

    CredentialService.save(
        PROVIDER,
        {
            "app_key": "k",
            "app_secret": "s",
            "refresh_token": "valid-refresh-token",
        },
    )

    ConfigurationService.save(
        InstallationConfig(
            storage_backend="dropbox",
            storage_root=tmp_path / "SaveCloud",
            version_retention=2,
        )
    )

    DropboxStorageBackend.reset()

    game = register_game(working_save)

    play_sessions(game, working_save, 6)

    versions = {
        path.split("/versions/")[1].split("/")[0]
        for path in fake.files
        if "/versions/" in path
    }

    assert len(versions) == 2


#
# Conflict resolution must not lose the archived save
#


def test_a_conflict_archive_survives_retention(registered_game, working_save):
    """
    Resolving a conflict preserves the losing save as a version. That
    version is the newest, so retention must not immediately discard it.
    """

    from savecloud.services.sync import ConflictResolution
    from tests.test_sync import advance_remote

    play_sessions(registered_game, working_save, 3)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    SyncService.sync(
        RegistryService.load_game(GAME_ID),
        ConflictResolution.LOCAL,
    )

    game = RegistryService.load_game(GAME_ID)

    archived = [
        read_save(SaveCloudLibrary.version_directory(GAME_ID, version))
        for version in SaveService.list_versions(game)
    ]

    assert "remote progress" in archived


#
# CLI
#


def test_cli_shows_retention():

    result = runner.invoke(app, ["config", "retention"])

    assert result.exit_code == 0
    assert "2 versions" in result.output


def test_cli_sets_retention():

    result = runner.invoke(app, ["config", "retention", "5"])

    assert result.exit_code == 0
    assert ConfigurationService.load().version_retention == 5


def test_cli_reports_unlimited_retention():

    runner.invoke(app, ["config", "retention", "0"])

    result = runner.invoke(app, ["config", "retention"])

    assert result.exit_code == 0
    assert "every version" in result.output.lower()


def test_cli_rejects_a_negative_retention():

    result = runner.invoke(app, ["config", "retention", "-1"])

    assert result.exit_code != 0

    assert ConfigurationService.load().version_retention == 2


def test_config_show_includes_retention():

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "Version History" in result.output


def test_device_profiles_are_untouched_by_retention(registered_game, working_save):
    """
    Retention affects saves, not configuration.
    """

    play_sessions(registered_game, working_save, 5)

    assert DeviceService.exists(SaveCloudLibrary.device_id(), GAME_ID)


#
# Applying a changed window
#
# Versions are trimmed as they are created, which never reaches a game
# whose save has not changed since. Lowering the window would then
# appear to do nothing until the next play session.
#


def test_lowering_the_window_prunes_an_untouched_game(
    registered_game,
    working_save,
):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 6)

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 6

    #
    # No save changes between here and the assertion: only the setting.
    #

    result = runner.invoke(app, ["config", "retention", "2"])

    assert result.exit_code == 0

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 2


def test_lowering_the_window_prunes_storage(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 6)

    remote = LocalStorageBackend.versions_directory(GAME_ID)

    assert len([path for path in remote.iterdir() if path.is_dir()]) == 6

    runner.invoke(app, ["config", "retention", "2"])

    assert len([path for path in remote.iterdir() if path.is_dir()]) == 2


def test_applying_the_window_keeps_the_newest(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 5)

    runner.invoke(app, ["config", "retention", "2"])

    game = RegistryService.load_game(GAME_ID)

    versions = SaveService.list_versions(game)

    newest = read_save(SaveCloudLibrary.version_directory(GAME_ID, versions[-1]))

    assert newest == "session 4"


def test_raising_the_window_removes_nothing(registered_game, working_save):

    play_sessions(registered_game, working_save, 4)

    before = SaveService.list_versions(RegistryService.load_game(GAME_ID))

    runner.invoke(app, ["config", "retention", "9"])

    assert SaveService.list_versions(RegistryService.load_game(GAME_ID)) == before


def test_unlimited_retention_removes_nothing(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 4)

    result = runner.invoke(app, ["config", "retention", "0"])

    assert result.exit_code == 0

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 4


def test_the_command_reports_what_it_removed(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 6)

    result = runner.invoke(app, ["config", "retention", "2"])

    assert GAME_ID in result.output
    assert "locally" in result.output
    assert "storage" in result.output


def test_the_setting_survives_unreachable_storage(
    registered_game,
    working_save,
    monkeypatch,
):
    """
    A backend that cannot be reached must not lose the setting.
    """

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 5)

    def unavailable(cls) -> bool:
        return False

    monkeypatch.setattr(
        LocalStorageBackend,
        "available",
        classmethod(unavailable),
    )

    result = runner.invoke(app, ["config", "retention", "2"])

    assert result.exit_code == 0

    assert ConfigurationService.load().version_retention == 2

    #
    # The library is local, so it is trimmed regardless.
    #

    assert len(SaveService.list_versions(RegistryService.load_game(GAME_ID))) == 2

    assert "next upload" in result.output


def test_apply_retention_reports_per_game(registered_game, working_save):

    ConfigurationService.set_retention(0)

    play_sessions(registered_game, working_save, 5)

    removed = SaveService.apply_retention(2)

    assert removed[GAME_ID] == [1, 2, 3]


def test_apply_retention_omits_games_with_nothing_to_remove(
    registered_game,
    working_save,
):

    play_sessions(registered_game, working_save, 3)

    assert SaveService.apply_retention(2) == {}


def test_prune_remote_omits_games_with_nothing_to_remove(
    registered_game,
    working_save,
):

    play_sessions(registered_game, working_save, 3)

    assert SyncService.prune_remote(2) == {}
