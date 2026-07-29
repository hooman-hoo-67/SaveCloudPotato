"""
Tests for the Dropbox storage backend.

Everything runs against an in-memory fake, so no credentials, network,
or Dropbox account is involved.
"""

from __future__ import annotations

import json

import pytest

from savecloud.models.installation_config import InstallationConfig
from savecloud.services.configuration import ConfigurationService
from savecloud.services.credentials import CredentialService
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import SyncAction, SyncService
from savecloud.storage import StorageRegistry
from savecloud.storage.dropbox import (
    PROVIDER,
    DropboxError,
    DropboxStorageBackend,
)
from savecloud.utils import http

from tests.conftest import GAME_ID, read_save, register_game, write_save
from tests.fake_dropbox import FakeDropbox


@pytest.fixture
def dropbox(monkeypatch, tmp_path):
    """
    Configure Dropbox as the active backend, with working credentials.
    """

    fake = FakeDropbox().install(monkeypatch)

    CredentialService.save(
        PROVIDER,
        {
            "app_key": "an-app-key",
            "app_secret": "an-app-secret",
            "refresh_token": "valid-refresh-token",
        },
    )

    ConfigurationService.save(
        InstallationConfig(
            storage_backend="dropbox",
            storage_root=tmp_path / "SaveCloud",
        )
    )

    DropboxStorageBackend.reset()

    return fake


#
# Credentials
#


def test_credentials_round_trip():

    CredentialService.save("example", {"token": "secret"})

    assert CredentialService.load("example") == {"token": "secret"}


def test_credentials_are_owner_only():
    """
    A refresh token grants access to someone's cloud storage.
    """

    CredentialService.save("example", {"token": "secret"})

    mode = CredentialService.path("example").stat().st_mode

    assert mode & 0o077 == 0


def test_credentials_of_an_unknown_provider_are_empty():

    assert CredentialService.load("nobody") == {}


def test_corrupt_credentials_do_not_raise():

    CredentialService.save("example", {"token": "secret"})

    CredentialService.path("example").write_text("{ broken", encoding="utf-8")

    assert CredentialService.load("example") == {}


def test_credentials_live_outside_synchronized_directories():
    """
    providers/ is never synchronized; registry/ and library/ are.
    """

    from savecloud.config.constants import (
        library_dir,
        provider_dir,
        registry_dir,
    )

    path = CredentialService.path(PROVIDER)

    assert path.parent == provider_dir()
    assert library_dir() not in path.parents
    assert registry_dir() not in path.parents


#
# Availability
#


def test_unavailable_without_credentials():

    ConfigurationService.set_backend("dropbox")

    assert not DropboxStorageBackend.available()

    assert "not set up" in DropboxStorageBackend.unavailable_reason()


def test_available_with_credentials(dropbox):

    assert DropboxStorageBackend.available()


def test_a_revoked_refresh_token_is_reported(monkeypatch, dropbox):

    CredentialService.update(PROVIDER, refresh_token="revoked")

    DropboxStorageBackend.reset()

    assert not DropboxStorageBackend.available()


def test_an_unreachable_dropbox_is_reported(monkeypatch, dropbox):

    def offline(*args, **kwargs):
        raise http.HttpError(0, "Network is unreachable", "https://api.dropboxapi.com")

    monkeypatch.setattr(http, "post_form", offline)

    DropboxStorageBackend.reset()

    assert not DropboxStorageBackend.available()

    assert "could not be reached" in DropboxStorageBackend.unavailable_reason()


def test_the_backend_is_registered():

    assert StorageRegistry.get("dropbox") is DropboxStorageBackend


def test_the_backend_declares_it_needs_setup():

    assert DropboxStorageBackend.requires_setup()

    from savecloud.storage import LocalStorageBackend

    assert not LocalStorageBackend.requires_setup()


def test_operations_without_credentials_explain_themselves():

    DropboxStorageBackend.reset()

    with pytest.raises(DropboxError, match="config provider dropbox"):
        DropboxStorageBackend.client()


#
# Token handling
#


def test_the_access_token_is_reused(dropbox):

    client = DropboxStorageBackend.client()

    client.access_token()
    client.access_token()
    client.access_token()

    #
    # Refreshing per call would triple every operation's latency.
    #

    assert dropbox.token_refreshes == 1


def test_an_expired_access_token_is_refreshed(dropbox):

    client = DropboxStorageBackend.client()

    client.access_token()

    client._expires_at = 0

    client.access_token()

    assert dropbox.token_refreshes == 2


#
# Remote layout
#


def test_the_remote_root_uses_the_configured_folder_name(dropbox):

    assert DropboxStorageBackend.root() == "/SaveCloud"


def test_an_inherited_filesystem_root_becomes_a_dropbox_folder(tmp_path):
    """
    storage_root is a local path for other backends. Switching to
    Dropbox must not recreate that whole path inside Dropbox.
    """

    ConfigurationService.save(
        InstallationConfig(
            storage_backend="dropbox",
            storage_root=tmp_path / "deep" / "nested" / "SaveCloudRemote",
        )
    )

    assert DropboxStorageBackend.root() == "/SaveCloudRemote"


def test_the_layout_matches_the_filesystem_backend(dropbox):
    """
    A library synchronized through Dropbox is arranged the same way as
    one synchronized through a shared folder.
    """

    assert DropboxStorageBackend.game_path(GAME_ID) == f"/SaveCloud/games/{GAME_ID}"
    assert DropboxStorageBackend.current_path(GAME_ID).endswith("/current")
    assert DropboxStorageBackend.versions_path(GAME_ID).endswith("/versions")
    assert DropboxStorageBackend.state_path(GAME_ID).endswith("/state.json")


#
# Transfer
#


def test_nothing_exists_before_upload(dropbox, registered_game):

    assert not DropboxStorageBackend.exists(GAME_ID)

    assert DropboxStorageBackend.state(GAME_ID) is None

    assert DropboxStorageBackend.list_games() == []


def test_upload_then_exists(dropbox, registered_game):

    SyncService.sync(registered_game)

    assert DropboxStorageBackend.exists(GAME_ID)

    assert DropboxStorageBackend.list_games() == [GAME_ID]


def test_upload_stores_the_save_contents(dropbox, registered_game):

    SyncService.sync(registered_game)

    assert dropbox.files[f"/SaveCloud/games/{GAME_ID}/current/save.dat"] == b"original"


def test_upload_records_remote_state(dropbox, registered_game):

    SyncService.sync(registered_game)

    state = DropboxStorageBackend.state(GAME_ID)

    assert state is not None
    assert state.game_id == GAME_ID
    assert state.checksum == SaveService.checksum(registered_game)


def test_upload_publishes_registry_documents(dropbox, registered_game):

    SyncService.sync(registered_game)

    assert f"/SaveCloud/games/{GAME_ID}/manifest.json" in dropbox.files
    assert f"/SaveCloud/games/{GAME_ID}/runtime.json" in dropbox.files


def test_upload_handles_nested_directories(dropbox, registered_game, working_save):

    (working_save / "profile" / "slot1").mkdir(parents=True)

    (working_save / "profile" / "slot1" / "deep.dat").write_text(
        "nested",
        encoding="utf-8",
    )

    SyncService.sync(registered_game)

    remote = f"/SaveCloud/games/{GAME_ID}/current/profile/slot1/deep.dat"

    assert dropbox.files[remote] == b"nested"


def test_download_restores_the_library(dropbox, registered_game):

    import shutil

    SyncService.sync(registered_game)

    shutil.rmtree(SaveService.current_save(registered_game))

    DropboxStorageBackend.download(GAME_ID)

    assert read_save(SaveService.current_save(registered_game)) == "original"


def test_download_restores_nested_directories(
    dropbox,
    registered_game,
    working_save,
):

    import shutil

    (working_save / "profile").mkdir()

    (working_save / "profile" / "deep.dat").write_text("nested", encoding="utf-8")

    SyncService.sync(registered_game)

    shutil.rmtree(SaveService.current_save(registered_game))

    DropboxStorageBackend.download(GAME_ID)

    current = SaveService.current_save(registered_game)

    assert (current / "profile" / "deep.dat").read_text(encoding="utf-8") == "nested"


def test_download_rejects_a_missing_remote(dropbox, registered_game):

    with pytest.raises(FileNotFoundError):
        DropboxStorageBackend.download(GAME_ID)


def test_a_deleted_file_is_removed_from_the_remote(
    dropbox,
    registered_game,
    working_save,
):
    """
    Uploading must not leave files a save no longer contains.
    """

    (working_save / "extra.dat").write_text("temporary", encoding="utf-8")

    SyncService.sync(registered_game)

    assert f"/SaveCloud/games/{GAME_ID}/current/extra.dat" in dropbox.files

    (working_save / "extra.dat").unlink()

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert f"/SaveCloud/games/{GAME_ID}/current/extra.dat" not in dropbox.files
    assert f"/SaveCloud/games/{GAME_ID}/current/save.dat" in dropbox.files


def test_versions_are_uploaded(dropbox, registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "second")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    versions = [
        path
        for path in dropbox.files
        if f"/games/{GAME_ID}/versions/" in path
    ]

    assert versions


def test_existing_versions_are_not_re_uploaded(
    dropbox,
    registered_game,
    working_save,
):
    """
    Versions are immutable, so a re-upload must leave them untouched.
    """

    SyncService.sync(registered_game)

    dropbox.uploads.clear()

    write_save(working_save, "second")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    reuploaded = [
        path for path in dropbox.uploads if "/versions/000001/" in path
    ]

    assert reuploaded == []


def test_delete_removes_the_game(dropbox, registered_game):

    SyncService.sync(registered_game)

    DropboxStorageBackend.delete(GAME_ID)

    assert not DropboxStorageBackend.exists(GAME_ID)

    assert not [
        path for path in dropbox.files if f"/games/{GAME_ID}/" in path
    ]


def test_delete_tolerates_a_missing_game(dropbox, registered_game):

    DropboxStorageBackend.delete(GAME_ID)


def test_fetch_current_does_not_touch_the_library(
    dropbox,
    registered_game,
    tmp_path,
):

    SyncService.sync(registered_game)

    write_save(SaveService.current_save(registered_game), "local-only")

    destination = tmp_path / "fetched"

    DropboxStorageBackend.fetch_current(GAME_ID, destination)

    assert read_save(destination) == "original"
    assert read_save(SaveService.current_save(registered_game)) == "local-only"


def test_corrupt_remote_state_is_treated_as_absent(dropbox, registered_game):

    SyncService.sync(registered_game)

    dropbox.put(
        DropboxStorageBackend.state_path(GAME_ID),
        b"{ not json",
    )

    assert DropboxStorageBackend.state(GAME_ID) is None


def test_a_large_file_is_refused_rather_than_truncated(dropbox, registered_game):

    from savecloud.storage.dropbox import MAX_UPLOAD_BYTES

    client = DropboxStorageBackend.client()

    with pytest.raises(DropboxError, match="limit"):
        client.upload("/SaveCloud/big.dat", b"x" * (MAX_UPLOAD_BYTES + 1))


#
# Synchronization through the service layer
#


def test_sync_uploads_through_dropbox(dropbox, registered_game):

    assert SyncService.sync(registered_game) is SyncAction.UPLOAD


def test_sync_is_a_no_op_when_unchanged(dropbox, registered_game):

    SyncService.sync(registered_game)

    assert SyncService.sync(RegistryService.load_game(GAME_ID)) is (
        SyncAction.UP_TO_DATE
    )


def test_sync_downloads_a_remote_change(dropbox, registered_game, working_save):
    """
    Simulates another device having uploaded.
    """

    from savecloud.models.remote_state import RemoteState
    from savecloud.utils.hashing import hash_directory

    SyncService.sync(registered_game)

    dropbox.put(
        f"/SaveCloud/games/{GAME_ID}/current/save.dat",
        b"progress from elsewhere",
    )

    #
    # Recompute the state the other device would have written.
    #

    import tempfile
    from pathlib import Path

    scratch = Path(tempfile.mkdtemp())

    (scratch / "save.dat").write_bytes(b"progress from elsewhere")

    state = RemoteState.create(
        game_id=GAME_ID,
        checksum=hash_directory(scratch),
        version=1,
        device_id="other-device",
        device_name="Other",
    )

    dropbox.put(
        DropboxStorageBackend.state_path(GAME_ID),
        json.dumps(state.to_dict()).encode("utf-8"),
    )

    action = SyncService.sync(RegistryService.load_game(GAME_ID))

    assert action is SyncAction.DOWNLOAD

    assert read_save(working_save) == "progress from elsewhere"


def test_a_save_survives_dropbox_being_unavailable(
    monkeypatch,
    dropbox,
    registered_game,
    working_save,
):
    """
    The library is the source of truth whether or not storage works.
    """

    from savecloud.services.autosync import AutoSyncService

    def offline(*args, **kwargs):
        raise http.HttpError(0, "Network is unreachable", "https://api.dropboxapi.com")

    monkeypatch.setattr(http, "post_form", offline)

    DropboxStorageBackend.reset()

    game = register_game(working_save, game_id="offline-game")

    result = AutoSyncService.play(game)

    assert result.exit_code == 0
    assert result.uploaded is False

    assert read_save(SaveService.current_save(game)) == "original"

    assert RegistryService.load_runtime("offline-game").pending_upload


#
# Two devices sharing one Dropbox account
#


def test_two_devices_share_saves_through_dropbox(monkeypatch, tmp_path):
    """
    The Milestone 9 interop story, over Dropbox instead of a folder.
    """

    from savecloud.models.device_profile import DeviceProfile
    from savecloud.services.device import DeviceService
    from savecloud.services.library import SaveCloudLibrary

    FakeDropbox().install(monkeypatch)

    def use_device(name: str):
        """
        Switch to a device's installation, creating it if needed.
        """

        monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / f"{name}-home"))

        SaveCloudLibrary.initialize()

        CredentialService.save(
            PROVIDER,
            {
                "app_key": "an-app-key",
                "app_secret": "an-app-secret",
                "refresh_token": "valid-refresh-token",
            },
        )

        ConfigurationService.save(
            InstallationConfig(
                storage_backend="dropbox",
                storage_root=tmp_path / "SaveCloud",
            )
        )

        DropboxStorageBackend.reset()

    desktop_save = tmp_path / "desktop-save"
    deck_save = tmp_path / "deck-save"

    #
    # Desktop registers and uploads.
    #

    use_device("desktop")

    write_save(desktop_save, "chapter one")

    game = register_game(desktop_save)

    assert SyncService.sync(game) is SyncAction.UPLOAD

    #
    # The Deck has never seen this game.
    #

    use_device("deck")

    assert not RegistryService.exists(GAME_ID)

    assert SyncService.remote_games() == [GAME_ID]

    SyncService.adopt(GAME_ID)

    assert RegistryService.exists(GAME_ID)

    DeviceService.create_profile(
        DeviceProfile(
            device_id=SaveCloudLibrary.device_id(),
            device_name=SaveCloudLibrary.device_name(),
            game_id=GAME_ID,
            working_save_path=deck_save,
            launch_command="true",
        )
    )

    SaveService.export_save(RegistryService.load_game(GAME_ID), (
        DeviceService.load_profile(SaveCloudLibrary.device_id(), GAME_ID)
    ))

    assert read_save(deck_save) == "chapter one"

    #
    # Play on the Deck, push it back.
    #

    write_save(deck_save, "chapter two, on the couch")

    assert SyncService.sync(RegistryService.load_game(GAME_ID)) is SyncAction.UPLOAD

    #
    # Return to the desktop.
    #

    use_device("desktop")

    assert SyncService.sync(RegistryService.load_game(GAME_ID)) is SyncAction.DOWNLOAD

    assert read_save(desktop_save) == "chapter two, on the couch"


def test_playing_on_both_devices_conflicts_through_dropbox(monkeypatch, tmp_path):

    from savecloud.models.device_profile import DeviceProfile
    from savecloud.services.device import DeviceService
    from savecloud.services.library import SaveCloudLibrary
    from savecloud.services.sync import SyncConflictError

    FakeDropbox().install(monkeypatch)

    def use_device(name: str):
        monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / f"{name}-home"))
        SaveCloudLibrary.initialize()
        CredentialService.save(
            PROVIDER,
            {
                "app_key": "k",
                "app_secret": "s",
                "refresh_token": "valid-refresh-token",
            },
        )
        ConfigurationService.save(
            InstallationConfig(
                storage_backend="dropbox",
                storage_root=tmp_path / "SaveCloud",
            )
        )
        DropboxStorageBackend.reset()

    desktop_save = tmp_path / "desktop-save"
    deck_save = tmp_path / "deck-save"

    use_device("desktop")
    write_save(desktop_save, "shared start")
    game = register_game(desktop_save)
    SyncService.sync(game)

    use_device("deck")
    SyncService.adopt(GAME_ID)
    DeviceService.create_profile(
        DeviceProfile(
            device_id=SaveCloudLibrary.device_id(),
            device_name=SaveCloudLibrary.device_name(),
            game_id=GAME_ID,
            working_save_path=deck_save,
            launch_command="true",
        )
    )
    SaveService.export_save(
        RegistryService.load_game(GAME_ID),
        DeviceService.load_profile(SaveCloudLibrary.device_id(), GAME_ID),
    )
    SyncService.sync(RegistryService.load_game(GAME_ID))

    #
    # Both play without synchronizing in between.
    #

    use_device("desktop")
    write_save(desktop_save, "desktop ending")
    SyncService.sync(RegistryService.load_game(GAME_ID))

    use_device("deck")
    write_save(deck_save, "deck ending")

    with pytest.raises(SyncConflictError):
        SyncService.sync(RegistryService.load_game(GAME_ID))

    #
    # Neither save was destroyed.
    #

    assert read_save(deck_save) == "deck ending"
