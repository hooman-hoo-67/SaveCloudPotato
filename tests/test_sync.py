"""
Test SyncService upload workflow.

Run with:

python tests/test_sync.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
    SyncStatus,
)
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import SyncService
from savecloud.storage.local import LocalStorageBackend

GAME_ID = "sync-test"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def cleanup(game: Game) -> None:
    """
    Remove any existing test data.
    """

    RegistryService.delete_registry(
        game.manifest.game_id,
    )

    SaveCloudLibrary.delete_game_library(
        game.manifest.game_id,
    )

    DeviceService.delete_profile(
        SaveCloudLibrary.device_id(),
        game.manifest.game_id,
    )

    remote = LocalStorageBackend.game_directory(
        game.manifest.game_id,
    )

    if remote.exists():
        shutil.rmtree(remote)

    working = Path.home() / "SaveCloudSyncTest"

    if working.exists():
        shutil.rmtree(working)


def main() -> None:

    section("TEST 1 - CREATE GAME")

    manifest = GameManifest(
        game_id=GAME_ID,
        display_name="Sync Test",
        launch_type=LaunchType.MANUAL,
        platform=Platform.NATIVE,
        adapter="eden",
        storage_backend="local",
    )

    runtime = GameRuntime()

    game = Game(
        manifest=manifest,
        runtime=runtime,
    )

    cleanup(game)

    print("✓ Game created")

    #
    # Working save
    #

    section("TEST 2 - CREATE WORKING SAVE")

    working_save = Path.home() / "SaveCloudSyncTest"

    working_save.mkdir(
        parents=True,
        exist_ok=True,
    )

    (working_save / "save.dat").write_text(
        "SaveCloud Test Save",
        encoding="utf-8",
    )

    print("✓ Working save created")

    #
    # Registry
    #

    section("TEST 3 - CREATE REGISTRY")

    RegistryService.create_registry(
        game,
    )

    print("✓ Registry created")

    #
    # Library
    #

    section("TEST 4 - CREATE LIBRARY")

    SaveCloudLibrary.create_game_library(
        game,
    )

    print("✓ Library created")

    #
    # Device profile
    #

    section("TEST 5 - CREATE DEVICE PROFILE")

    profile = DeviceProfile(
        device_id=SaveCloudLibrary.device_id(),
        device_name=SaveCloudLibrary.device_name(),
        game_id=GAME_ID,
        working_save_path=working_save,
        launch_command="dummy",
    )

    DeviceService.create_profile(
        profile,
    )

    print("✓ Device profile created")

    #
    # Upload
    #

    section("TEST 6 - UPLOAD")

    SyncService.upload(
        game,
    )

    print("✓ Upload completed")

    #
    # Verify remote storage
    #

    section("TEST 7 - VERIFY REMOTE STORAGE")

    assert LocalStorageBackend.exists(
        game,
    )

    print("✓ Remote save exists")

    #
    # Verify runtime
    #

    section("TEST 8 - VERIFY RUNTIME")

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    assert loaded.runtime.status == SyncStatus.SYNCED

    assert loaded.runtime.pending_upload is False

    assert loaded.runtime.last_device == SaveCloudLibrary.device_id()

    assert loaded.runtime.last_sync is not None

    print("✓ Runtime updated")

    #
    # Verify snapshot
    #

    section("TEST 9 - VERIFY SNAPSHOT")

    versions = SaveService.list_versions(
        loaded,
    )

    assert versions == [1]

    print("✓ Snapshot created")

    #
    # Verify metadata
    #

    section("TEST 10 - VERIFY METADATA")

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.last_import is not None

    print("✓ Metadata updated")
    section("TEST 11 - MODIFY WORKING SAVE")

    (working_save / "save.dat").write_text(
        "Modified Save",
        encoding="utf-8",
    )

    assert (working_save / "save.dat").read_text(
        encoding="utf-8",
    ) == "Modified Save"

    print("✓ Working save modified")

    section("TEST 12 - DOWNLOAD")

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    SyncService.download(
        loaded,
    )

    print("✓ Download completed")

    section("TEST 13 - VERIFY WORKING SAVE")

    contents = (working_save / "save.dat").read_text(
        encoding="utf-8",
    )

    assert contents == "SaveCloud Test Save"

    print("✓ Working save restored")

    section("TEST 14 - VERIFY RUNTIME")

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    assert loaded.runtime.status == SyncStatus.SYNCED

    assert loaded.runtime.pending_upload is False

    assert loaded.runtime.last_device == SaveCloudLibrary.device_id()

    assert loaded.runtime.last_sync is not None

    print("✓ Runtime updated")

    section("TEST 15 - VERIFY EXPORT METADATA")

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.last_export is not None

    print("✓ Export metadata updated")

    section("TEST 16 - SYNC DOWNLOAD PATH")

    #
    # Working save currently contains the remote contents.
    # Change it so we can verify sync() restores it.
    #

    (working_save / "save.dat").write_text(
        "Modified Again",
        encoding="utf-8",
    )

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    SyncService.sync(
        loaded,
    )

    contents = (working_save / "save.dat").read_text(
        encoding="utf-8",
    )

    assert contents == "SaveCloud Test Save"

    print("✓ sync() selected download()")

    section("TEST 17 - SYNC UPLOAD PATH")

    #
    # Modify the working save.
    #

    (working_save / "save.dat").write_text(
        "Newest Save",
        encoding="utf-8",
    )

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    loaded.runtime.mark_pending()

    RegistryService.update_runtime(
        loaded,
    )

    SyncService.sync(
        loaded,
    )

    #
    # Download immediately afterwards to verify the
    # remote was updated.
    #

    SyncService.download(
        loaded,
    )

    contents = (working_save / "save.dat").read_text(
        encoding="utf-8",
    )

    assert contents == "Newest Save"

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    assert loaded.runtime.status == SyncStatus.SYNCED
    assert loaded.runtime.pending_upload is False

    print("✓ sync() selected upload()")

    section("TEST 18 - MISSING REMOTE")

    LocalStorageBackend.delete(
        loaded,
    )

    assert not LocalStorageBackend.exists(
        loaded,
    )

    SyncService.sync(
        loaded,
    )

    assert LocalStorageBackend.exists(
        loaded,
    )

    print("✓ sync() uploaded missing remote")

    section("TEST 19 - NO CHANGE UPLOAD")

    #
    # Record current version.
    #

    metadata_before = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    latest_before = metadata_before.latest_version

    #
    # Upload again without modifying anything.
    #

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    SyncService.upload(
        loaded,
    )

    #
    # Verify no new snapshot was created.
    #

    metadata_after = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata_after.latest_version == latest_before

    print("✓ Upload skipped because no changes were detected")

    section("TEST 20 - CLEANUP")

    cleanup(
        loaded,
    )

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
