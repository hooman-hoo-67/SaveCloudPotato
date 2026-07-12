"""
Test the play CLI command.

Run with:

python tests/test_cli_play.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from savecloud.commands.play import play
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
from savecloud.services.sync import SyncService

GAME_ID = "cli-play-test"


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

    working = Path.home() / "SaveCloudCLIPlay"

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

    section("TEST 1 - CREATE GAME")

    manifest = GameManifest(
        game_id=GAME_ID,
        display_name="CLI Play Test",
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

    section("TEST 2 - CREATE WORKING SAVE")

    working = Path.home() / "SaveCloudCLIPlay"

    working.mkdir(
        parents=True,
        exist_ok=True,
    )

    (working / "save.dat").write_text(
        "CLI Play",
        encoding="utf-8",
    )

    print("✓ Working save created")

    section("TEST 3 - CREATE REGISTRY")

    RegistryService.create_registry(
        game,
    )

    SaveCloudLibrary.create_game_library(
        game,
    )

    print("✓ Registry created")

    section("TEST 4 - CREATE PROFILE")

    profile = DeviceProfile(
        device_id=SaveCloudLibrary.device_id(),
        device_name=SaveCloudLibrary.device_name(),
        game_id=GAME_ID,
        working_save_path=working,
        launch_command="sleep 2",
    )

    DeviceService.create_profile(
        profile,
    )

    print("✓ Profile created")

    section("TEST 5 - INITIAL UPLOAD")

    SyncService.upload(
        game,
    )

    print("✓ Initial upload complete")

    section("TEST 6 - CLI PLAY")

    play(
        GAME_ID,
    )

    print("✓ CLI play completed")

    section("TEST 7 - CLEANUP")

    cleanup(
        game,
    )

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
