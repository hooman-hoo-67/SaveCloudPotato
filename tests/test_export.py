"""
Test SaveService.export_save().

Run with:

python tests/test_export.py
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

TEST_SAVE_DIR = Path("/tmp/savecloud-export-test")


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

    SaveCloudLibrary.delete_game_library(GAME_ID)

    #
    # Create dummy working save
    #

    TEST_SAVE_DIR.mkdir(parents=True)

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
    # Import save into library
    #

    section("TEST 3 - IMPORT")

    SaveCloudLibrary.create_game_library(game)

    SaveService.import_save(
        game,
        profile,
    )

    print("✓ Save imported")

    #
    # Delete working save
    #

    section("TEST 4 - DELETE WORKING SAVE")

    shutil.rmtree(TEST_SAVE_DIR)

    assert not TEST_SAVE_DIR.exists()

    print("✓ Working save removed")

    #
    # Export save back
    #

    section("TEST 5 - EXPORT")

    SaveService.export_save(
        game,
        profile,
    )

    assert TEST_SAVE_DIR.exists()

    assert (TEST_SAVE_DIR / "save.dat").exists()

    assert (TEST_SAVE_DIR / "settings.ini").exists()

    print("✓ Save exported")

    #
    # Verify contents
    #

    section("TEST 6 - VERIFY CONTENTS")

    assert (TEST_SAVE_DIR / "save.dat").read_text(
        encoding="utf-8",
    ) == "pokemon save"

    assert (TEST_SAVE_DIR / "settings.ini").read_text(
        encoding="utf-8",
    ) == "graphics=high"

    print("✓ File contents verified")

    #
    # Validation
    #

    section("TEST 7 - MISSING MANAGED SAVE")

    shutil.rmtree(SaveService.current_save(game))

    assert not SaveService.current_save(game).exists()

    try:
        SaveService.export_save(
            game,
            profile,
        )
    except FileNotFoundError:
        print("✓ Correct exception raised")
    else:
        raise AssertionError("Expected FileNotFoundError")

    #
    # Cleanup
    #

    section("TEST 8 - CLEANUP")

    if TEST_SAVE_DIR.exists():
        shutil.rmtree(TEST_SAVE_DIR)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
