"""
Backend integration test for SaveCloud.

Run with:

python tests/test_backend.py
"""

from pathlib import Path

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


GAME_ID = "pokemon-scarlet"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:

    #
    # Installation
    #

    section("TEST 1 - INSTALLATION")

    metadata = SaveCloudLibrary.installation_metadata()

    print(f"Device Name : {metadata['device_name']}")
    print(f"Device ID   : {metadata['device_id']}")

    print("✓ Installation metadata loaded")

    #
    # Game
    #

    section("TEST 2 - GAME MODEL")

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
    # Game Library
    #

    section("TEST 3 - GAME LIBRARY")

    SaveCloudLibrary.create_game_library(game)

    library = SaveCloudLibrary.library_directory(GAME_ID)

    assert library.exists()
    assert SaveCloudLibrary.current_directory(GAME_ID).exists()
    assert SaveCloudLibrary.versions_directory(GAME_ID).exists()
    assert SaveCloudLibrary.metadata_path(GAME_ID).exists()

    print("✓ Library created")
    print("✓ Current directory exists")
    print("✓ Versions directory exists")
    print("✓ Metadata exists")

    #
    # Registry
    #

    section("TEST 4 - REGISTRY")

    RegistryService.create_registry(game)

    loaded_game = RegistryService.load_game(GAME_ID)

    assert loaded_game.manifest == manifest

    print("✓ Registry saved")
    print("✓ Registry loaded")

    #
    # Device Profile
    #

    section("TEST 5 - DEVICE PROFILE")

    profile = DeviceProfile(
        device_id=metadata["device_id"],
        device_name=metadata["device_name"],
        game_id=GAME_ID,
        working_save_path=Path("/tmp/pokemon-save"),
        launch_command="steam://rungameid/123456",
    )

    DeviceService.create_profile(profile)

    loaded_profile = DeviceService.load_profile(
        metadata["device_id"],
        GAME_ID,
    )

    assert loaded_profile.device_id == profile.device_id
    assert loaded_profile.game_id == profile.game_id
    assert (
        loaded_profile.working_save_path
        == profile.working_save_path
    )

    print("✓ Device profile saved")
    print("✓ Device profile loaded")

    #
    # Cleanup
    #

    section("TEST 6 - CLEANUP")

    DeviceService.delete_profile(
        metadata["device_id"],
        GAME_ID,
    )

    RegistryService.delete_registry(GAME_ID)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    assert not SaveCloudLibrary.library_directory(GAME_ID).exists()

    print("✓ Device profile removed")
    print("✓ Registry removed")
    print("✓ Library removed")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
