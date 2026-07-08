"""
Test the SaveService.

Run with:

python tests/test_save_service.py
"""

from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.services.save import SaveService

GAME_ID = "pokemon-scarlet"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
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

    section("TEST 2 - CURRENT SAVE DIRECTORY")

    current = SaveService.current_save(game)

    print(f"Current save directory: {current}")

    expected = "current"

    assert current.name == expected

    print("✓ Correct directory returned")

    section("TEST 3 - VERIFY GAME ID")

    assert current.parent.name == GAME_ID

    print("✓ Correct game library")

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
