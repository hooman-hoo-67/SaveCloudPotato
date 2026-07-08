"""
Test SaveService.create_version().

Run with:

python tests/test_versioning.py
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

TEST_SAVE_DIR = Path("/tmp/savecloud-version-test")


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
    # Create dummy save
    #

    TEST_SAVE_DIR.mkdir(parents=True)

    section("TEST 1 - CREATE DUMMY SAVE")

    (TEST_SAVE_DIR / "save.dat").write_text(
        "pokemon save",
        encoding="utf-8",
    )

    print("✓ Dummy save created")

    #
    # Create game
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
    # Create library
    #

    section("TEST 3 - IMPORT SAVE")

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

    version = SaveCloudLibrary.version_directory(
        GAME_ID,
        1,
    )

    assert version.exists()

    assert (version / "save.dat").exists()

    print("✓ Version created")

    #
    # Verify metadata
    #

    section("TEST 5 - VERIFY METADATA")

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.current_version == 0

    assert metadata.latest_version == 1

    print("✓ Metadata updated")

    #
    # Cleanup
    #

    section("TEST 6 - CLEANUP")

    shutil.rmtree(TEST_SAVE_DIR)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
