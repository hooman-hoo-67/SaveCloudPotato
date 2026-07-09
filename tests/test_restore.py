"""
Test SaveService.restore_version().

Run with:

python tests/test_restore.py
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

TEST_SAVE_DIR = Path("/tmp/savecloud-restore-test")


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:

    #
    # Cleanup
    #

    if TEST_SAVE_DIR.exists():
        shutil.rmtree(TEST_SAVE_DIR)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    #
    # Create original save
    #

    TEST_SAVE_DIR.mkdir(parents=True)

    section("TEST 1 - CREATE ORIGINAL SAVE")

    (TEST_SAVE_DIR / "save.dat").write_text(
        "original save",
        encoding="utf-8",
    )

    print("✓ Original save created")

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
    # Import save
    #

    section("TEST 3 - IMPORT")

    SaveCloudLibrary.create_game_library(game)

    SaveService.import_save(
        game,
        profile,
    )

    print("✓ Save imported")

    #
    # Create version
    #

    section("TEST 4 - CREATE VERSION")

    SaveService.create_version(game)

    print("✓ Version created")

    #
    # Modify current save
    #

    section("TEST 5 - MODIFY CURRENT SAVE")

    current = SaveService.current_save(game)

    (current / "save.dat").write_text(
        "modified save",
        encoding="utf-8",
    )

    print("✓ Current save modified")

    #
    # Restore
    #

    section("TEST 6 - RESTORE VERSION")

    SaveService.restore_version(
        game,
        1,
    )

    print("✓ Version restored")

    #
    # Verify restored contents
    #

    section("TEST 7 - VERIFY")

    restored = (SaveService.current_save(game) / "save.dat").read_text(
        encoding="utf-8",
    )

    assert restored == "original save"

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.current_version == 1
    assert metadata.latest_version == 1

    print("✓ Original contents restored")
    print("✓ Metadata updated")

    #
    # Validation
    #

    section("TEST 8 - INVALID VERSION")

    try:
        SaveService.restore_version(
            game,
            999,
        )
    except FileNotFoundError:
        print("✓ Correct exception raised")
    else:
        raise AssertionError("Expected FileNotFoundError")

    #
    # Cleanup
    #

    section("TEST 9 - CLEANUP")

    shutil.rmtree(TEST_SAVE_DIR)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
