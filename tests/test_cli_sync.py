"""
Test synchronization CLI commands.

Run with:

python tests/test_cli_sync.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from savecloud.commands.download import download
from savecloud.commands.sync import sync
from savecloud.commands.upload import upload
from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.storage.local import LocalStorageBackend

GAME_ID = "cli-sync-test"


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

    remote = LocalStorageBackend.game_directory(
        game.manifest.game_id,
    )

    if remote.exists():
        shutil.rmtree(remote)

    working = Path.home() / "SaveCloudCliTest"

    if working.exists():
        shutil.rmtree(working)


def main() -> None:

    section("TEST 1 - CREATE GAME")

    manifest = GameManifest(
        game_id=GAME_ID,
        display_name="CLI Sync Test",
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

    working_save = Path.home() / "SaveCloudCliTest"

    working_save.mkdir(
        parents=True,
        exist_ok=True,
    )

    (working_save / "save.dat").write_text(
        "CLI Test Save",
        encoding="utf-8",
    )

    RegistryService.create_registry(
        game,
    )

    SaveCloudLibrary.create_game_library(
        game,
    )

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

    print("✓ Test environment created")

    #
    # Upload command
    #

    section("TEST 2 - CLI UPLOAD")

    upload(
        GAME_ID,
    )

    assert LocalStorageBackend.exists(
        game,
    )

    print("✓ upload command")

    #
    # Download command
    #

    section("TEST 3 - CLI DOWNLOAD")

    (working_save / "save.dat").write_text(
        "Wrong Save",
        encoding="utf-8",
    )

    download(
        GAME_ID,
    )

    assert (working_save / "save.dat").read_text(
        encoding="utf-8",
    ) == "CLI Test Save"

    print("✓ download command")

    #
    # Sync command
    #

    section("TEST 4 - CLI SYNC")

    sync(
        GAME_ID,
    )

    print("✓ sync command")

    #
    # Cleanup
    #

    section("TEST 5 - CLEANUP")

    cleanup(
        game,
    )

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
