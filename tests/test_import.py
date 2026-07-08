"""
Test SaveService.import_save().

Run with:

python tests/test_import.py
"""

from pathlib import Path
import shutil

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.save import SaveService

GAME_ID = "pokemon-scarlet"

TEST_SAVE_DIR = Path("/tmp/savecloud-import-test")


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:

    #
    # Cleanup previous test
    #

    if TEST_SAVE_DIR.exists():
        shutil.rmtree(TEST_SAVE_DIR)

    TEST_SAVE_DIR.mkdir(parents=True)

    #
    # Create dummy save files
    #

    section("TEST 1 - CREATE DUMMY SAVE")

    (TEST_SAVE_DIR / "save.dat").write_text(
        "pokemon save",
        encoding="utf-8",
    )

    (TEST_SAVE_DIR / "settings.ini").write_text(
        "graphics=high",
        encoding="utf-8",
    )

    print("✓ Dummy save created")

    #
    # Create Game
    #

    section("TEST 2 - CREATE GAME")

    manifest = GameManifest(
        game_id=GAME_ID,
        display_name="Pokemon Scarlet",
        launch_type=LaunchType.STEAM,
        platform=Platform.EMULATOR,
        adapter="eden",
        storage_backend="syncthing",
    )

    runtime = GameRuntime()

    game = Game(
        manifest=manifest,
        runtime=runtime,
    )

    profile = DeviceProfile(
        device_id=SaveCloudLibrary.device_id(),
        device_name=SaveCloudLibrary.device_name(),
        game_id=GAME_ID,
        working_save_path=TEST_SAVE_DIR,
        launch_command="steam://dummy",
    )

    print("✓ Game created")

    #
    # Import
    #

    section("TEST 3 - IMPORT SAVE")

    SaveCloudLibrary.create_game_library(game)

    SaveService.import_save(
        game,
        profile,
    )

    current = SaveService.current_save(game)

    assert current.exists()

    assert (current / "save.dat").exists()

    assert (current / "settings.ini").exists()

    print("✓ Save imported")

    #
    # Cleanup
    #

    section("TEST 4 - CLEANUP")

    shutil.rmtree(TEST_SAVE_DIR)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
