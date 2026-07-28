"""
Tests for the automatic synchronization workflow.
"""

from __future__ import annotations

import pytest

from savecloud.services.autosync import AutoSyncService
from savecloud.services.configuration import ConfigurationService
from savecloud.services.launch import LaunchService
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import (
    ConflictResolution,
    SyncAction,
    SyncConflictError,
    SyncService,
)
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, read_save, register_game, write_save
from tests.test_sync import advance_remote


def playing_command(working_save, contents: str) -> str:
    """
    Build a launch command that writes save data, like a real game.
    """

    return f"sh -c \"printf '{contents}' > {working_save / 'save.dat'}\""


@pytest.fixture
def game_that_saves(tmp_path):
    """
    Register a game whose launch command writes new save data.
    """

    working = tmp_path / "working"

    write_save(working, "before playing")

    return register_game(
        working,
        launch_command=playing_command(working, "after playing"),
    )


def test_play_uploads_progress(game_that_saves, working_save):

    result = AutoSyncService.play(game_that_saves)

    assert result.exit_code == 0
    assert result.uploaded is True
    assert result.warnings == []

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "after playing"


def test_play_synchronizes_before_launching(game_that_saves):

    result = AutoSyncService.play(game_that_saves)

    #
    # Nothing was in storage, so the pre-launch sync uploaded.
    #

    assert result.pre_launch is SyncAction.UPLOAD


def test_play_pulls_remote_progress_before_launching(tmp_path, monkeypatch):

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(working, launch_command="true")

    SyncService.sync(game)

    advance_remote(GAME_ID, "progress from elsewhere")

    result = AutoSyncService.play(RegistryService.load_game(GAME_ID))

    assert result.pre_launch is SyncAction.DOWNLOAD

    #
    # The game would have launched with the newest save in place.
    #

    assert read_save(working) == "progress from elsewhere"


def test_play_creates_a_version_for_the_session(game_that_saves):

    AutoSyncService.play(game_that_saves)

    game = RegistryService.load_game(GAME_ID)

    versions = SaveService.list_versions(game)

    assert len(versions) >= 1

    assert read_save(SaveService.current_save(game)) == "after playing"


def test_a_crash_does_not_upload(tmp_path):

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(working, launch_command="false")

    result = AutoSyncService.play(game)

    assert result.exit_code == 1
    assert result.uploaded is False

    #
    # A crashed game may have written a half-finished save, so only
    # what the pre-launch sync uploaded is in storage.
    #

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


def test_a_crash_is_recorded_in_the_runtime(tmp_path):

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(working, launch_command="false")

    AutoSyncService.play(game)

    runtime = RegistryService.load_runtime(GAME_ID)

    assert runtime.last_exit_code == 1
    assert "exited with code 1" in (runtime.last_error or "")


def test_play_works_offline(game_that_saves):
    """
    An unreachable backend must never stop someone playing.
    """

    ConfigurationService.set_backend("syncthing")

    result = AutoSyncService.play(game_that_saves)

    assert result.exit_code == 0
    assert result.uploaded is False

    assert any("offline" in warning for warning in result.warnings)


def test_an_offline_session_is_kept_for_later_upload(game_that_saves):

    ConfigurationService.set_backend("syncthing")

    AutoSyncService.play(game_that_saves)

    runtime = RegistryService.load_runtime(GAME_ID)

    assert runtime.pending_upload is True

    #
    # The save itself is safe in the library.
    #

    game = RegistryService.load_game(GAME_ID)

    assert read_save(SaveService.current_save(game)) == "after playing"


def test_a_pending_session_uploads_once_storage_returns(game_that_saves):

    ConfigurationService.set_backend("syncthing")

    AutoSyncService.play(game_that_saves)

    ConfigurationService.set_backend("local")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "after playing"


def test_a_conflict_prevents_launching(tmp_path, monkeypatch, working_save):

    game = register_game(working_save, launch_command="true")

    SyncService.sync(game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    launched = []

    monkeypatch.setattr(
        LaunchService,
        "launch",
        staticmethod(lambda profile: launched.append(profile)),
    )

    with pytest.raises(SyncConflictError):
        AutoSyncService.play(RegistryService.load_game(GAME_ID))

    #
    # Playing would build new progress on top of an unresolved
    # conflict, so the game must not start.
    #

    assert launched == []


def test_a_resolved_conflict_allows_launching(tmp_path, working_save):

    game = register_game(
        working_save,
        launch_command=playing_command(working_save, "after resolving"),
    )

    SyncService.sync(game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    result = AutoSyncService.play(
        RegistryService.load_game(GAME_ID),
        ConflictResolution.LOCAL,
    )

    assert result.exit_code == 0
    assert result.uploaded is True


def test_sync_disabled_games_only_launch(tmp_path):

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(
        working,
        launch_command=playing_command(working, "played"),
        sync_enabled=False,
    )

    result = AutoSyncService.play(game)

    assert result.exit_code == 0
    assert result.pre_launch is None
    assert result.uploaded is False

    assert not LocalStorageBackend.exists(GAME_ID)
