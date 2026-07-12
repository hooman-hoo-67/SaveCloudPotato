"""
Test AutoSyncService.

Run with:

python tests/test_autosync.py
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
from savecloud.services.autosync import AutoSyncService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService

GAME_ID = "autosync-test"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def cleanup(game: Game) -> None:

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

    working = Path.home() / "SaveCloudAutoSyncTest"

    if working.exists():
        shutil.rmtree(working)

    backend = SyncService.backend(
        game,
    )

    remote = backend.game_directory(
        game.manifest.game_id,
    )

    if remote.exists():
        shutil.rmtree(remote)


def main() -> None:

    #
    # Create game
    #

    section("TEST 1 - CREATE GAME")

    manifest = GameManifest(
        game_id=GAME_ID,
        display_name="AutoSync Test",
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

    working_save = Path.home() / "SaveCloudAutoSyncTest"

    working_save.mkdir(
        parents=True,
        exist_ok=True,
    )

    (working_save / "save.dat").write_text(
        "AutoSync Save",
        encoding="utf-8",
    )

    print("✓ Working save created")

    #
    # Registry / Library
    #

    section("TEST 3 - CREATE REGISTRY")

    RegistryService.create_registry(
        game,
    )

    SaveCloudLibrary.create_game_library(
        game,
    )

    print("✓ Registry created")

    #
    # Device profile
    #

    section("TEST 4 - CREATE PROFILE")

    profile = DeviceProfile(
        device_id=SaveCloudLibrary.device_id(),
        device_name=SaveCloudLibrary.device_name(),
        game_id=GAME_ID,
        working_save_path=working_save,
        launch_command="sleep 2",
    )

    DeviceService.create_profile(
        profile,
    )

    print("✓ Profile created")

    #
    # Initial upload
    #

    section("TEST 5 - INITIAL UPLOAD")

    SyncService.upload(
        game,
    )

    print("✓ Initial upload complete")

    #
    # Automatic workflow
    #

    section("TEST 6 - PLAY")

    exit_code = AutoSyncService.play(
        game,
    )

    assert exit_code == 0

    print("✓ Game launched and exited successfully")

    #
    # Verify runtime
    #

    section("TEST 7 - VERIFY RUNTIME")

    loaded = RegistryService.load_game(
        GAME_ID,
    )

    #
    # Final runtime state.
    #

    assert loaded.runtime.status == SyncStatus.SYNCED

    assert loaded.runtime.pending_upload is False

    #
    # Launch lifecycle.
    #

    assert loaded.runtime.last_launch is not None

    assert loaded.runtime.last_exit is not None

    assert loaded.runtime.last_exit_code == 0

    #
    # Synchronization.
    #

    assert loaded.runtime.last_sync is not None

    assert loaded.runtime.last_device == SaveCloudLibrary.device_id()

    print("✓ Runtime lifecycle verified")

    #
    # Verify remote still exists
    #

    section("TEST 8 - VERIFY REMOTE")

    backend = SyncService.backend(
        loaded,
    )

    assert backend.exists(
        loaded,
    )

    print("✓ Remote save exists")

    #
    # Cleanup
    #

    section("TEST 9 - CLEANUP")

    cleanup(
        loaded,
    )

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
