"""
Test LocalStorageBackend.

Run with:

python tests/test_local_storage.py
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
from savecloud.storage.local import LocalStorageBackend

GAME_ID = "pokemon-scarlet"

TEST_SAVE_DIR = Path("/tmp/savecloud-storage-test")


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

    remote = LocalStorageBackend.game_directory(GAME_ID)

    if remote.exists():
        shutil.rmtree(remote)

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
        storage_backend="local",
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

    SaveCloudLibrary.create_game_library(game)

    shutil.copytree(
        TEST_SAVE_DIR,
        SaveCloudLibrary.current_directory(GAME_ID),
        dirs_exist_ok=True,
    )

    print("✓ Game created")

    #
    # Upload
    #

    section("TEST 3 - UPLOAD")

    LocalStorageBackend.upload(game)

    remote_current = LocalStorageBackend.game_directory(GAME_ID) / "current"

    assert remote_current.exists()

    assert (remote_current / "save.dat").exists()

    assert (remote_current / "settings.ini").exists()

    print("✓ Upload successful")

    #
    # Verify upload replaces old files
    #

    section("TEST 4 - REPLACE REMOTE SAVE")

    (remote_current / "stale.txt").write_text(
        "old file",
        encoding="utf-8",
    )

    assert (remote_current / "stale.txt").exists()

    LocalStorageBackend.upload(game)

    assert not (remote_current / "stale.txt").exists()

    print("✓ Old files removed")

    #
    # Download
    #

    section("TEST 5 - DOWNLOAD")

    shutil.rmtree(SaveCloudLibrary.current_directory(GAME_ID))

    assert not SaveCloudLibrary.current_directory(GAME_ID).exists()

    LocalStorageBackend.download(game)

    current = SaveCloudLibrary.current_directory(GAME_ID)

    assert current.exists()

    assert (current / "save.dat").exists()

    assert (current / "settings.ini").exists()

    print("✓ Download successful")

    #
    # Verify contents
    #

    section("TEST 6 - VERIFY CONTENTS")

    assert (current / "save.dat").read_text(
        encoding="utf-8",
    ) == "pokemon save"

    assert (current / "settings.ini").read_text(
        encoding="utf-8",
    ) == "graphics=high"

    print("✓ Contents verified")

    #
    # Upload validation
    #

    section("TEST 7 - MISSING MANAGED SAVE")

    shutil.rmtree(current)

    assert not current.exists()

    try:
        LocalStorageBackend.upload(game)
    except FileNotFoundError:
        print("✓ Correct exception raised")
    else:
        raise AssertionError("Expected FileNotFoundError")

    #
    # Download validation
    #

    section("TEST 8 - MISSING REMOTE SAVE")

    remote_current = LocalStorageBackend.game_directory(GAME_ID) / "current"

    shutil.rmtree(remote_current)

    assert not remote_current.exists()

    try:
        LocalStorageBackend.download(game)
    except FileNotFoundError:
        print("✓ Correct exception raised")
    else:
        raise AssertionError("Expected FileNotFoundError")

    #
    # Cleanup
    #

    section("TEST 9 - CLEANUP")

    if TEST_SAVE_DIR.exists():
        shutil.rmtree(TEST_SAVE_DIR)

    if remote.exists():
        shutil.rmtree(remote)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    print("✓ Cleanup complete")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
