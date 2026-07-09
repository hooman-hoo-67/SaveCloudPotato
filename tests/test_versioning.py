"""
Test SaveService versioning.

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
    # Import save
    #

    section("TEST 3 - IMPORT SAVE")

    SaveCloudLibrary.create_game_library(game)

    SaveService.import_save(
        game,
        profile,
    )

    print("✓ Save imported")

    #
    # Create versions
    #

    section("TEST 4 - CREATE VERSIONS")

    SaveService.create_version(game)
    SaveService.create_version(game)
    SaveService.create_version(game)

    print("✓ Versions created")

    #
    # Verify version directories
    #

    section("TEST 5 - VERIFY VERSION DIRECTORIES")

    for version in (1, 2, 3):
        version_directory = SaveCloudLibrary.version_directory(
            GAME_ID,
            version,
        )

        assert version_directory.exists()
        assert (version_directory / "save.dat").exists()

    print("✓ Version directories verified")

    #
    # Verify metadata
    #

    section("TEST 6 - VERIFY METADATA")

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.current_version == 0
    assert metadata.latest_version == 3

    print("✓ Metadata verified")

    #
    # List versions
    #

    section("TEST 7 - LIST VERSIONS")

    versions = SaveService.list_versions(game)

    assert versions == [1, 2, 3]

    print(f"Versions: {versions}")
    print("✓ Versions listed correctly")

    #
    # Version exists
    #

    section("TEST 8 - VERSION EXISTS")

    assert SaveService.version_exists(game, 1)
    assert SaveService.version_exists(game, 2)
    assert SaveService.version_exists(game, 3)

    assert not SaveService.version_exists(game, 4)
    assert not SaveService.version_exists(game, 999)

    print("✓ Existing versions detected")
    print("✓ Missing versions rejected")

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
