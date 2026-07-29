"""
Tests for the storage backend framework.
"""

from __future__ import annotations

import pytest

from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.save import SaveService
from savecloud.storage import (
    LocalStorageBackend,
    StorageRegistry,
    SyncthingStorageBackend,
    backend_exists,
    get_backend,
)
from savecloud.storage.syncthing import FOLDER_MARKER

from tests.conftest import GAME_ID, read_save, write_save


@pytest.fixture
def uploaded(registered_game, device_id):
    """
    Register a game and upload its save to local storage.
    """

    profile = DeviceService.load_profile(device_id, GAME_ID)

    SaveService.import_save(registered_game, profile)

    LocalStorageBackend.upload(registered_game)

    return registered_game


#
# Registry
#


def test_registry_lookup():

    assert backend_exists("local")
    assert backend_exists("syncthing")
    assert get_backend("local") is LocalStorageBackend
    assert backend_exists("dropbox")
    assert not backend_exists("nonexistent-provider")
    assert get_backend("nonexistent-provider") is None


def test_registry_lookup_is_case_insensitive():

    assert StorageRegistry.get("LOCAL") is LocalStorageBackend


def test_registry_names():

    assert StorageRegistry.names() == ["dropbox", "local", "syncthing"]


def test_a_new_backend_needs_no_service_changes():
    """
    The extension point the architecture depends on.
    """

    class MemoryBackend(LocalStorageBackend):

        @staticmethod
        def display_name() -> str:
            return "Memory"

    StorageRegistry.register("memory", MemoryBackend)

    try:
        ConfigurationService.set_backend("memory")

        assert StorageRegistry.resolve() is MemoryBackend

    finally:
        StorageRegistry.backends().pop("memory", None)
        StorageRegistry._BACKENDS.pop("memory", None)


#
# Local backend
#


def test_local_backend_uses_the_configured_root(storage_root):

    assert LocalStorageBackend.storage_root() == storage_root


def test_changing_the_root_moves_the_backend(tmp_path):

    ConfigurationService.set_root(tmp_path / "elsewhere")

    assert LocalStorageBackend.storage_root() == tmp_path / "elsewhere"


def test_exists_is_false_before_upload(registered_game):

    assert not LocalStorageBackend.exists(GAME_ID)


def test_upload_then_exists(uploaded):

    assert LocalStorageBackend.exists(GAME_ID)

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


def test_upload_records_remote_state(uploaded):

    state = LocalStorageBackend.state(GAME_ID)

    assert state is not None
    assert state.game_id == GAME_ID
    assert state.checksum == SaveService.checksum(uploaded)


def test_upload_publishes_registry_documents(uploaded):
    """
    Registry documents travel with the save so other devices can adopt
    the game without registering it again.
    """

    remote = LocalStorageBackend.game_directory(GAME_ID)

    assert (remote / "manifest.json").exists()
    assert (remote / "runtime.json").exists()


def test_download_restores_the_library(uploaded):

    import shutil

    shutil.rmtree(SaveService.current_save(uploaded))

    LocalStorageBackend.download(GAME_ID)

    assert read_save(SaveService.current_save(uploaded)) == "original"


def test_download_rejects_a_missing_remote(registered_game):

    with pytest.raises(FileNotFoundError):
        LocalStorageBackend.download(GAME_ID)


def test_versions_are_uploaded(registered_game, device_id, working_save):

    profile = DeviceService.load_profile(device_id, GAME_ID)

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    LocalStorageBackend.upload(registered_game)

    assert (LocalStorageBackend.versions_directory(GAME_ID) / "000001").exists()


def test_existing_versions_are_not_re_uploaded(
    registered_game,
    device_id,
    working_save,
):
    """
    Versions are immutable, so a re-upload must leave them untouched.
    """

    profile = DeviceService.load_profile(device_id, GAME_ID)

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    LocalStorageBackend.upload(registered_game)

    remote_version = LocalStorageBackend.versions_directory(GAME_ID) / "000001"

    marker = remote_version / "marker"

    marker.write_text("untouched", encoding="utf-8")

    LocalStorageBackend.upload(registered_game)

    assert marker.read_text(encoding="utf-8") == "untouched"


def test_fetch_current_does_not_touch_the_library(uploaded, tmp_path):

    write_save(SaveService.current_save(uploaded), "local-only")

    destination = tmp_path / "fetched"

    LocalStorageBackend.fetch_current(GAME_ID, destination)

    assert read_save(destination) == "original"
    assert read_save(SaveService.current_save(uploaded)) == "local-only"


def test_delete_removes_the_remote(uploaded):

    LocalStorageBackend.delete(GAME_ID)

    assert not LocalStorageBackend.exists(GAME_ID)


def test_delete_tolerates_a_missing_remote(registered_game):

    LocalStorageBackend.delete(GAME_ID)


def test_metadata_requires_a_remote(registered_game):

    with pytest.raises(FileNotFoundError):
        LocalStorageBackend.metadata(GAME_ID)


def test_list_games(uploaded):

    assert LocalStorageBackend.list_games() == [GAME_ID]


def test_list_games_is_empty_without_a_root():

    assert LocalStorageBackend.list_games() == []


def test_local_backend_creates_its_root(storage_root):

    assert LocalStorageBackend.available()
    assert storage_root.is_dir()


#
# Syncthing backend
#


def test_syncthing_requires_a_shared_folder(storage_root):

    ConfigurationService.set_backend("syncthing")

    storage_root.mkdir(parents=True, exist_ok=True)

    #
    # A plain directory is not a Syncthing folder.
    #

    assert not SyncthingStorageBackend.available()
    assert "not a Syncthing folder" in SyncthingStorageBackend.unavailable_reason()


def test_syncthing_is_available_with_the_folder_marker(storage_root):

    storage_root.mkdir(parents=True, exist_ok=True)

    (storage_root / FOLDER_MARKER).mkdir()

    assert SyncthingStorageBackend.available()


def test_syncthing_never_creates_its_root(storage_root):
    """
    Creating the root would produce a folder Syncthing never replicates.
    """

    assert not SyncthingStorageBackend.available()
    assert not storage_root.exists()

    assert "does not exist" in SyncthingStorageBackend.unavailable_reason()


def test_syncthing_surfaces_conflict_files(storage_root):

    storage_root.mkdir(parents=True, exist_ok=True)

    (storage_root / FOLDER_MARKER).mkdir()

    game_directory = SyncthingStorageBackend.ensure_game_directory(GAME_ID)

    conflict = game_directory / "save.sync-conflict-20260101-120000-ABCDEFG.dat"

    conflict.write_text("other device", encoding="utf-8")

    assert SyncthingStorageBackend.conflicts(GAME_ID) == [conflict]
    assert conflict in SyncthingStorageBackend.conflicts()


def test_syncthing_reports_no_conflicts_when_clean(storage_root):

    storage_root.mkdir(parents=True, exist_ok=True)

    (storage_root / FOLDER_MARKER).mkdir()

    assert SyncthingStorageBackend.conflicts() == []
