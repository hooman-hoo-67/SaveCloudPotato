"""
Tests for the RegistryService.
"""

from __future__ import annotations

import json

from savecloud.models.game import SyncStatus
from savecloud.services.registry import RegistryService

from tests.conftest import GAME_ID, build_game


def test_create_and_load_registry():

    game = build_game()

    RegistryService.create_registry(game)

    assert RegistryService.exists(GAME_ID)
    assert RegistryService.registry_manifest_path(GAME_ID).exists()
    assert RegistryService.registry_runtime_path(GAME_ID).exists()

    loaded = RegistryService.load_game(GAME_ID)

    assert loaded.manifest == game.manifest


def test_delete_registry():

    RegistryService.create_registry(build_game())

    RegistryService.delete_registry(GAME_ID)

    assert not RegistryService.exists(GAME_ID)


def test_manifest_no_longer_stores_a_storage_backend():

    RegistryService.create_registry(build_game())

    data = json.loads(
        RegistryService.registry_manifest_path(GAME_ID).read_text(encoding="utf-8"),
    )

    assert "storage_backend" not in data


def test_legacy_manifest_still_loads():
    """
    Manifests written before Milestone 8 carry a storage_backend field.
    """

    game = build_game()

    RegistryService.create_registry(game)

    path = RegistryService.registry_manifest_path(GAME_ID)

    data = json.loads(path.read_text(encoding="utf-8"))

    data["storage_backend"] = "syncthing"

    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = RegistryService.load_manifest(GAME_ID)

    assert loaded.game_id == GAME_ID
    assert not hasattr(loaded, "storage_backend")


def test_legacy_storage_backend_is_reported_for_migration():

    for game_id in ("one", "two"):

        game = build_game(game_id=game_id)

        RegistryService.create_registry(game)

        path = RegistryService.registry_manifest_path(game_id)

        data = json.loads(path.read_text(encoding="utf-8"))

        data["storage_backend"] = "syncthing"

        path.write_text(json.dumps(data), encoding="utf-8")

    assert RegistryService.legacy_storage_backend() == "syncthing"


def test_disagreeing_legacy_backends_are_not_migrated():

    for game_id, backend in (("one", "local"), ("two", "syncthing")):

        RegistryService.create_registry(build_game(game_id=game_id))

        path = RegistryService.registry_manifest_path(game_id)

        data = json.loads(path.read_text(encoding="utf-8"))

        data["storage_backend"] = backend

        path.write_text(json.dumps(data), encoding="utf-8")

    #
    # Picking one arbitrarily could silently redirect a game's saves.
    #

    assert RegistryService.legacy_storage_backend() is None


def test_legacy_storage_backend_is_none_without_legacy_data():

    RegistryService.create_registry(build_game())

    assert RegistryService.legacy_storage_backend() is None


def test_runtime_round_trips_the_sync_checksum():

    game = build_game()

    game.runtime.mark_synced("device-1", "abc123")

    RegistryService.create_registry(game)

    loaded = RegistryService.load_runtime(GAME_ID)

    assert loaded.last_sync_checksum == "abc123"
    assert loaded.status is SyncStatus.SYNCED
    assert loaded.last_device == "device-1"


def test_runtime_without_a_checksum_loads_as_none():

    RegistryService.create_registry(build_game())

    assert RegistryService.load_runtime(GAME_ID).last_sync_checksum is None


def test_list_games_skips_directories_without_a_manifest():

    RegistryService.create_registry(build_game())

    RegistryService.registry_directory("stray").mkdir(parents=True)

    assert [game.manifest.game_id for game in RegistryService.list_games()] == [GAME_ID]


def test_list_games_is_empty_on_a_fresh_installation():

    assert RegistryService.list_games() == []
