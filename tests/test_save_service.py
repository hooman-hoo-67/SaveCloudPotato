"""
Tests for save import, export, versioning, and restore.
"""

from __future__ import annotations

import pytest

from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.save import SaveService

from tests.conftest import GAME_ID, read_save, write_save


@pytest.fixture
def profile(registered_game, device_id):
    """
    Return the registered game's device profile.
    """

    return DeviceService.load_profile(device_id, GAME_ID)


def test_import_copies_the_working_save(registered_game, profile):

    SaveService.import_save(registered_game, profile)

    assert read_save(SaveService.current_save(registered_game)) == "original"


def test_export_copies_back_to_the_working_save(
    registered_game,
    profile,
    working_save,
):

    SaveService.import_save(registered_game, profile)

    write_save(working_save, "clobbered")

    SaveService.export_save(registered_game, profile)

    assert read_save(working_save) == "original"


def test_import_rejects_a_missing_working_save(registered_game, profile):

    import shutil

    shutil.rmtree(profile.working_save_path)

    with pytest.raises(FileNotFoundError):
        SaveService.import_save(registered_game, profile)


def test_create_version_numbers_sequentially(registered_game, profile):

    SaveService.import_save(registered_game, profile)

    assert SaveService.create_version(registered_game) == 1
    assert SaveService.create_version(registered_game) == 2

    assert SaveService.list_versions(registered_game) == [1, 2]


def test_versions_capture_contents_at_the_time(
    registered_game,
    profile,
    working_save,
):

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    write_save(working_save, "second")

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    assert read_save(SaveCloudLibrary.version_directory(GAME_ID, 1)) == "original"
    assert read_save(SaveCloudLibrary.version_directory(GAME_ID, 2)) == "second"


def test_restore_brings_back_an_earlier_version(
    registered_game,
    profile,
    working_save,
):

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    write_save(working_save, "second")

    SaveService.import_save(registered_game, profile)

    SaveService.restore_version(registered_game, 1)

    assert read_save(SaveService.current_save(registered_game)) == "original"


def test_restore_preserves_the_save_it_replaces(
    registered_game,
    profile,
    working_save,
):
    """
    A restore must itself be reversible.
    """

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    write_save(working_save, "second")

    SaveService.import_save(registered_game, profile)

    SaveService.restore_version(registered_game, 1)

    versions = SaveService.list_versions(registered_game)

    #
    # Version 2 is the "second" save that the restore displaced.
    #

    assert versions == [1, 2]
    assert read_save(SaveCloudLibrary.version_directory(GAME_ID, 2)) == "second"


def test_versions_pulled_from_storage_are_never_overwritten(
    registered_game,
    profile,
    working_save,
):
    """
    A device that adopts a game receives version directories without
    its metadata having allocated those numbers. Allocating the next
    version from metadata alone would overwrite immutable history.
    """

    SaveService.import_save(registered_game, profile)

    for _ in range(3):
        SaveService.create_version(registered_game)

    original = read_save(SaveCloudLibrary.version_directory(GAME_ID, 1))

    #
    # Simulate the post-download state: versions on disk, metadata that
    # never learned about them.
    #

    metadata = SaveCloudLibrary.load_library_metadata(GAME_ID)

    metadata.latest_version = 0

    SaveCloudLibrary.save_library_metadata(GAME_ID, metadata)

    write_save(working_save, "new session")

    SaveService.import_save(registered_game, profile)

    created = SaveService.create_version(registered_game)

    assert created == 4

    assert read_save(SaveCloudLibrary.version_directory(GAME_ID, 1)) == original


def test_restore_rejects_an_unknown_version(registered_game):

    with pytest.raises(FileNotFoundError):
        SaveService.restore_version(registered_game, 99)


def test_version_exists(registered_game, profile):

    SaveService.import_save(registered_game, profile)

    SaveService.create_version(registered_game)

    assert SaveService.version_exists(registered_game, 1)
    assert not SaveService.version_exists(registered_game, 2)


def test_has_changes_detects_a_modified_working_save(
    registered_game,
    profile,
    working_save,
):

    SaveService.import_save(registered_game, profile)

    assert not SaveService.has_changes(registered_game, profile)

    write_save(working_save, "modified")

    assert SaveService.has_changes(registered_game, profile)


def test_has_changes_is_false_when_the_working_save_is_missing(
    registered_game,
    profile,
):
    """
    A missing working save must never be mistaken for an empty one.
    """

    import shutil

    SaveService.import_save(registered_game, profile)

    shutil.rmtree(profile.working_save_path)

    assert not SaveService.has_changes(registered_game, profile)


def test_ensure_game_library_does_not_clobber_metadata(registered_game):

    SaveCloudLibrary.set_current_version(GAME_ID, 7)

    SaveCloudLibrary.ensure_game_library(GAME_ID)

    assert SaveCloudLibrary.load_library_metadata(GAME_ID).current_version == 7


def test_ensure_game_library_creates_a_missing_library():

    SaveCloudLibrary.ensure_game_library("brand-new")

    assert SaveCloudLibrary.current_directory("brand-new").exists()
    assert SaveCloudLibrary.metadata_path("brand-new").exists()
