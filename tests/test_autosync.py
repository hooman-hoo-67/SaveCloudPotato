"""
Tests for the automatic synchronization workflow.
"""

from __future__ import annotations

import signal

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


#
# Exit classification
#
# A game closed from Gaming Mode arrives as a signal death, not a
# clean zero. Treating that as a crash would mean saves never publish
# on a Steam Deck, where it is the usual way to close a game.
#


def test_a_crash_is_still_captured_locally(tmp_path):
    """
    A crash is when the session is least reproducible, so discarding
    it is the worst available response.
    """

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(working, launch_command="false")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    write_save(working, "progress then crash")

    AutoSyncService.play(RegistryService.load_game(GAME_ID))

    assert read_save(SaveService.current_save(game)) == "progress then crash"


def test_a_crash_leaves_the_save_pending(tmp_path):
    """
    Captured but unpublished, so an explicit sync still sends it.
    """

    working = tmp_path / "working"

    write_save(working, "original")

    register_game(working, launch_command="false")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    write_save(working, "progress then crash")

    AutoSyncService.play(RegistryService.load_game(GAME_ID))

    runtime = RegistryService.load_runtime(GAME_ID)

    assert runtime.pending_upload is True

    assert "exited with code 1" in (runtime.last_error or "")

    #
    # The player decides the save is good; sync publishes it.
    #

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert read_save(
        LocalStorageBackend.current_directory(GAME_ID)
    ) == "progress then crash"


def test_a_crash_warns_how_to_publish_the_save(tmp_path):

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(working, launch_command="false")

    result = AutoSyncService.play(game)

    assert any("savecloud sync" in warning for warning in result.warnings)


def test_termination_counts_as_an_ordinary_exit():
    """
    Steam's Stop button and Gaming Mode's Exit Game both send SIGTERM.
    """

    from savecloud.services.autosync import _is_ordinary_exit

    assert _is_ordinary_exit(0) is True

    assert _is_ordinary_exit(-int(signal.SIGTERM)) is True
    assert _is_ordinary_exit(-int(signal.SIGINT)) is True

    assert _is_ordinary_exit(1) is False
    assert _is_ordinary_exit(-int(signal.SIGSEGV)) is False


def test_a_terminated_game_is_uploaded(tmp_path):
    """
    The Gaming Mode case: closed by SIGTERM, and the save must publish.
    """

    working = tmp_path / "working"

    write_save(working, "original")

    register_game(working, launch_command="true")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    write_save(working, "played in gaming mode")

    from savecloud.services.autosync import PlayResult

    result = PlayResult(exit_code=0)

    AutoSyncService.after_exit(
        RegistryService.load_game(GAME_ID),
        -int(signal.SIGTERM),
        result,
    )

    assert result.uploaded is True

    assert read_save(
        LocalStorageBackend.current_directory(GAME_ID)
    ) == "played in gaming mode"


def test_signal_handlers_are_restored_after_a_launch(tmp_path):
    """
    The wrapper must not leave the process's signal disposition
    changed once the game has exited.
    """

    working = tmp_path / "working"

    write_save(working, "original")

    game = register_game(working, launch_command="true")

    before = signal.getsignal(signal.SIGTERM)

    AutoSyncService.play(game)

    assert signal.getsignal(signal.SIGTERM) is before


def test_a_shutdown_signal_reaches_the_game(tmp_path):
    """
    Steam signals SaveCloud, not the game. Without forwarding, the
    game would keep running and the save would never be captured.
    """

    import subprocess
    import sys
    import time

    working = tmp_path / "working"

    write_save(working, "original")

    marker = tmp_path / "handled.txt"

    #
    # A game that writes its save when asked to stop, as a real one
    # flushes on shutdown.
    #

    script = (
        "import signal, sys, time\n"
        f"open({str(marker)!r}, 'w').write('flushed')\n"
        "signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))\n"
        "time.sleep(30)\n"
    )

    process = subprocess.Popen([sys.executable, "-c", script])

    for _ in range(100):
        if marker.exists():
            break
        time.sleep(0.05)

    import threading

    def stop() -> None:
        time.sleep(0.2)
        process.send_signal(signal.SIGTERM)

    threading.Thread(target=stop, daemon=True).start()

    exit_code = AutoSyncService._wait_forwarding_signals(process)

    assert exit_code == 0

    assert marker.read_text() == "flushed"
