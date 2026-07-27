"""
Tests for the SyncService.

These cover the decision that matters most in SaveCloud: whether a
difference between two devices is a one-sided change that can be
applied automatically, or a genuine conflict that must not be resolved
by guessing.
"""

from __future__ import annotations

import json

import pytest

from savecloud.models.game import SyncStatus
from savecloud.models.remote_state import RemoteState
from savecloud.services.configuration import ConfigurationService
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import (
    ConflictResolution,
    StorageUnavailableError,
    SyncAction,
    SyncConflictError,
    SyncService,
)
from savecloud.storage import LocalStorageBackend
from savecloud.utils.hashing import hash_directory

from tests.conftest import GAME_ID, read_save, register_game, write_save


def advance_remote(
    game_id: str,
    contents: str,
    device_id: str = "other-device",
) -> str:
    """
    Simulate another device uploading a different save.

    Returns the new remote checksum.
    """

    remote = LocalStorageBackend.current_directory(game_id)

    write_save(remote, contents)

    checksum = hash_directory(remote)

    state = RemoteState.create(
        game_id=game_id,
        checksum=checksum,
        version=1,
        device_id=device_id,
        device_name="Other Device",
    )

    LocalStorageBackend.state_path(game_id).write_text(
        json.dumps(state.to_dict()),
        encoding="utf-8",
    )

    return checksum


#
# First synchronization
#


def test_first_sync_uploads(registered_game):

    assert SyncService.sync(registered_game) is SyncAction.UPLOAD

    assert LocalStorageBackend.exists(GAME_ID)
    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


def test_upload_records_the_sync_checksum(registered_game):

    SyncService.sync(registered_game)

    runtime = RegistryService.load_runtime(GAME_ID)

    assert runtime.status is SyncStatus.SYNCED
    assert runtime.last_sync_checksum == SaveService.checksum(registered_game)
    assert runtime.pending_upload is False


def test_upload_creates_a_version(registered_game):

    SyncService.sync(registered_game)

    assert SaveService.list_versions(registered_game) == [1]


#
# Steady state
#


def test_unchanged_sync_is_a_no_op(registered_game):

    SyncService.sync(registered_game)

    game = RegistryService.load_game(GAME_ID)

    assert SyncService.sync(game) is SyncAction.UP_TO_DATE

    #
    # No new version: nothing changed.
    #

    assert SaveService.list_versions(game) == [1]


def test_status_does_not_change_anything(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "modified")

    game = RegistryService.load_game(GAME_ID)

    assert SyncService.status(game) is SyncAction.UPLOAD

    #
    # A status check must not upload.
    #

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


#
# One-sided changes
#


def test_local_change_uploads(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "played some more")

    game = RegistryService.load_game(GAME_ID)

    assert SyncService.sync(game) is SyncAction.UPLOAD

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "played some more"


def test_remote_change_downloads(registered_game, working_save):

    SyncService.sync(registered_game)

    advance_remote(GAME_ID, "progress from the other device")

    game = RegistryService.load_game(GAME_ID)

    assert SyncService.sync(game) is SyncAction.DOWNLOAD

    assert read_save(working_save) == "progress from the other device"


def test_download_updates_the_sync_checksum(registered_game):

    SyncService.sync(registered_game)

    checksum = advance_remote(GAME_ID, "remote progress")

    game = RegistryService.load_game(GAME_ID)

    SyncService.sync(game)

    assert RegistryService.load_runtime(GAME_ID).last_sync_checksum == checksum


#
# Conflicts
#


def test_both_sides_changed_is_a_conflict(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    game = RegistryService.load_game(GAME_ID)

    assert SyncService.status(game) is SyncAction.CONFLICT

    with pytest.raises(SyncConflictError):
        SyncService.sync(game)


def test_a_conflict_changes_nothing(registered_game, working_save):
    """
    The whole point of aborting: neither save is touched.
    """

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    game = RegistryService.load_game(GAME_ID)

    with pytest.raises(SyncConflictError):
        SyncService.sync(game)

    assert read_save(working_save) == "local progress"
    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "remote progress"


def test_a_conflict_is_recorded_in_the_runtime(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    with pytest.raises(SyncConflictError):
        SyncService.sync(RegistryService.load_game(GAME_ID))

    assert RegistryService.load_runtime(GAME_ID).status is SyncStatus.CONFLICT


def test_an_unknown_ancestor_is_treated_as_a_conflict(registered_game, working_save):
    """
    Without a common ancestor there is no basis for choosing a side.
    """

    write_save(LocalStorageBackend.current_directory(GAME_ID), "pre-existing remote")

    advance_remote(GAME_ID, "pre-existing remote")

    game = RegistryService.load_game(GAME_ID)

    assert game.runtime.last_sync_checksum is None

    assert SyncService.status(game) is SyncAction.CONFLICT


def test_keep_local_wins_and_preserves_the_remote(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    game = RegistryService.load_game(GAME_ID)

    action = SyncService.sync(game, ConflictResolution.LOCAL)

    assert action is SyncAction.UPLOAD

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "local progress"

    #
    # The overwritten remote save must still be recoverable.
    #

    versions = SaveService.list_versions(game)

    archived = [
        read_save(SaveService.current_save(game).parent / "versions" / f"{v:06d}")
        for v in versions
    ]

    assert "remote progress" in archived


def test_keep_remote_wins_and_preserves_the_local_save(
    registered_game,
    working_save,
):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    game = RegistryService.load_game(GAME_ID)

    action = SyncService.sync(game, ConflictResolution.REMOTE)

    assert action is SyncAction.DOWNLOAD

    assert read_save(working_save) == "remote progress"

    versions = SaveService.list_versions(game)

    archived = [
        read_save(SaveService.current_save(game).parent / "versions" / f"{v:06d}")
        for v in versions
    ]

    #
    # The library held "original" when the conflict was resolved; the
    # displaced save is preserved rather than discarded.
    #

    assert len(versions) >= 2
    assert "original" in archived


def test_resolution_clears_the_conflict_state(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    SyncService.sync(
        RegistryService.load_game(GAME_ID),
        ConflictResolution.LOCAL,
    )

    assert RegistryService.load_runtime(GAME_ID).status is SyncStatus.SYNCED


#
# Backend availability
#


def test_sync_fails_clearly_when_storage_is_unavailable(registered_game):

    ConfigurationService.set_backend("syncthing")

    #
    # No Syncthing folder marker exists, so the backend is unusable.
    #

    with pytest.raises(StorageUnavailableError):
        SyncService.sync(registered_game)


def test_an_unavailable_backend_does_not_corrupt_the_library(registered_game):

    ConfigurationService.set_backend("syncthing")

    with pytest.raises(StorageUnavailableError):
        SyncService.upload(registered_game)

    assert SaveService.current_save(registered_game).exists()


#
# Bulk synchronization
#


def test_sync_all_covers_every_game(tmp_path):

    first = tmp_path / "working-one"
    second = tmp_path / "working-two"

    write_save(first, "one")
    write_save(second, "two")

    register_game(first, game_id="game-one")
    register_game(second, game_id="game-two")

    results = SyncService.sync_all()

    assert results == {
        "game-one": SyncAction.UPLOAD,
        "game-two": SyncAction.UPLOAD,
    }


def test_sync_all_skips_games_with_sync_disabled(tmp_path):

    working = tmp_path / "working-disabled"

    write_save(working, "data")

    register_game(working, game_id="disabled", sync_enabled=False)

    assert SyncService.sync_all() == {}


def test_sync_all_continues_past_a_failure(tmp_path, registered_game, monkeypatch):

    working = tmp_path / "working-broken"

    write_save(working, "data")

    register_game(working, game_id="broken")

    original = SyncService.upload

    def failing_upload(game):

        if game.manifest.game_id == "broken":
            raise RuntimeError("backend exploded")

        return original(game)

    monkeypatch.setattr(SyncService, "upload", staticmethod(failing_upload))

    results = SyncService.sync_all()

    assert results[GAME_ID] is SyncAction.UPLOAD
    assert "backend exploded" in results["broken"]
