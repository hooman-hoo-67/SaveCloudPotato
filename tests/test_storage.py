"""
Tests for the SaveCloud storage backend.
"""

from __future__ import annotations

import shutil

from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.storage import (
    backend_exists,
    get_backend,
)
from savecloud.storage.local import LocalStorageBackend


def create_game() -> Game:
    """
    Create a dummy game object.
    """

    manifest = GameManifest(
        game_id="storage_test",
        display_name="Storage Test",
        launch_type=LaunchType.MANUAL,
        platform=Platform.NATIVE,
        adapter="eden",
        storage_backend="local",
    )

    runtime = GameRuntime()

    return Game(
        manifest=manifest,
        runtime=runtime,
    )


def cleanup(game: Game) -> None:
    """
    Remove any existing test storage.
    """

    directory = LocalStorageBackend.game_directory(
        game.manifest.game_id,
    )

    if directory.exists():
        shutil.rmtree(directory)


def main() -> None:
    """
    Execute storage backend tests.
    """

    print()
    print("========== SaveCloud Storage Tests ==========")
    print()

    game = create_game()

    cleanup(game)

    #
    # Backend Registry
    #

    print("Testing backend registry...")

    assert backend_exists("local")
    assert get_backend("local") is LocalStorageBackend
    assert not backend_exists("banana")
    assert get_backend("banana") is None

    print("✓ Backend registry")

    #
    # Exists()
    #

    print("Testing exists()...")

    assert not LocalStorageBackend.exists(game)

    print("✓ exists()")

    #
    # Create fake remote save
    #

    print("Creating fake remote save...")

    remote = (
        LocalStorageBackend.ensure_game_directory(
            game.manifest.game_id,
        )
        / "current"
    )

    remote.mkdir(
        exist_ok=True,
    )

    (remote / "save.dat").write_text(
        "dummy save",
        encoding="utf-8",
    )

    print("✓ Fake save created")

    #
    # Exists again
    #

    print("Testing exists() after creation...")

    assert LocalStorageBackend.exists(game)

    print("✓ exists() after creation")

    #
    # Metadata
    #

    print("Testing metadata()...")

    metadata = LocalStorageBackend.metadata(game)

    assert isinstance(metadata, dict)
    assert "modified" in metadata

    print("✓ metadata()")

    #
    # Delete
    #

    print("Testing delete()...")

    LocalStorageBackend.delete(game)

    assert not LocalStorageBackend.exists(game)

    print("✓ delete()")

    #
    # Delete missing
    #

    print("Testing delete() on missing save...")

    LocalStorageBackend.delete(game)

    print("✓ delete() on missing save")

    #
    # Metadata missing
    #

    print("Testing metadata() on missing save...")

    try:
        LocalStorageBackend.metadata(game)

        raise AssertionError(
            "metadata() should have raised FileNotFoundError."
        )

    except FileNotFoundError:
        print("✓ metadata() raises FileNotFoundError")

    cleanup(game)

    print()
    print("=============================================")
    print(" All storage backend tests passed.")
    print("=============================================")
    print()


if __name__ == "__main__":
    main()