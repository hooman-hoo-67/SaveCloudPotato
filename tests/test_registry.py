"""
Development smoke test for the RegistryService.

Run with:

python tests/test_registry.py
"""

from pathlib import Path

from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)

from savecloud.services.registry import RegistryService

GAME_ID = "pokemon-scarlet"


def separator(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:

    separator("TEST 1 - CREATE GAME")

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

    print("✓ Game object created")

    separator("TEST 2 - CREATE REGISTRY")

    RegistryService.create_registry(game)

    registry = RegistryService.registry_directory(GAME_ID)

    print(f"Registry directory: {registry}")

    assert registry.exists()

    assert RegistryService.registry_manifest_path(GAME_ID).exists()

    assert RegistryService.registry_runtime_path(GAME_ID).exists()

    print("✓ Registry created")

    separator("TEST 3 - LOAD GAME")

    loaded = RegistryService.load_game(GAME_ID)

    print("✓ Loaded game")

    separator("TEST 4 - VERIFY DATA")

    assert loaded.manifest == manifest

    assert loaded.runtime.current_version == runtime.current_version

    assert loaded.runtime.status == runtime.status

    print("✓ Manifest matches")

    print("✓ Runtime matches")

    separator("TEST 5 - DELETE REGISTRY")

    RegistryService.delete_registry(GAME_ID)

    assert not RegistryService.exists(GAME_ID)

    print("✓ Registry deleted")

    separator("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
