"""
Test LibraryMetadata integration.

Run with:

python tests/test_library_metadata.py
"""

from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.models.library_metadata import LibraryMetadata
from savecloud.services.library import SaveCloudLibrary

GAME_ID = "pokemon-scarlet"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:

    #
    # Create Game
    #

    section("TEST 1 - CREATE GAME")

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

    print("✓ Game created")

    #
    # Create library
    #

    section("TEST 2 - CREATE LIBRARY")

    SaveCloudLibrary.delete_game_library(GAME_ID)
    SaveCloudLibrary.create_game_library(game)

    print("✓ Library created")

    #
    # Load metadata
    #

    section("TEST 3 - LOAD METADATA")

    metadata = SaveCloudLibrary.load_library_metadata(GAME_ID)

    assert isinstance(
        metadata,
        LibraryMetadata,
    )

    print("✓ Metadata loaded")

    #
    # Verify fields
    #

    section("TEST 4 - VERIFY DATA")

    assert metadata.current_version == runtime.current_version

    assert metadata.latest_version == runtime.current_version

    assert metadata.created_at

    assert metadata.last_import is None

    assert metadata.last_export is None

    print("✓ Metadata verified")

    #
    # Modify metadata
    #

    section("TEST 5 - SAVE METADATA")

    metadata.last_import = "2026-07-09T00:00:00Z"

    SaveCloudLibrary.save_library_metadata(
        GAME_ID,
        metadata,
    )

    reloaded = SaveCloudLibrary.load_library_metadata(GAME_ID)

    assert reloaded.last_import == "2026-07-09T00:00:00Z"

    print("✓ Metadata persisted")

    #
    # Test version path
    #

    section("TEST 6 - VERSION PATH")

    version_path = SaveCloudLibrary.version_directory(
        GAME_ID,
        7,
    )

    assert version_path.name == "000007"

    print(version_path)

    print("✓ Version path generated")

    section("TEST 7 - MARK IMPORT")

    SaveCloudLibrary.mark_import(
        GAME_ID,
    )

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.last_import is not None

    print("✓ Import timestamp updated")

    section("TEST 8 - MARK EXPORT")

    SaveCloudLibrary.mark_export(
        GAME_ID,
    )

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.last_export is not None

    print("✓ Export timestamp updated")


    section("TEST 9 - SET CURRENT VERSION")
    
    SaveCloudLibrary.set_current_version(
        GAME_ID,
        42,
    )

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert metadata.current_version == 42

    print("✓ Current version updated")
    #
    # Cleanup
    #

    section("TEST 10 - INCREMENT LATEST VERSION")

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    previous = metadata.latest_version

    new = SaveCloudLibrary.increment_latest_version(
        GAME_ID,
    )

    metadata = SaveCloudLibrary.load_library_metadata(
        GAME_ID,
    )

    assert new == previous + 1
    assert metadata.latest_version == previous + 1

    print("✓ Latest version incremented")


    section("TEST 11 - CLEANUP")

    SaveCloudLibrary.delete_game_library(GAME_ID)

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()

