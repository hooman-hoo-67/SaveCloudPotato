"""
End-to-end synchronization between two devices.

Two independent SaveCloud installations share one storage root, which
is exactly the desktop/Steam Deck arrangement Milestone 9 targets.
Nothing here reaches into internals: each device only uses the commands
a user would.
"""

from __future__ import annotations

import pytest

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.installation_config import InstallationConfig
from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import (
    ConflictResolution,
    SyncAction,
    SyncConflictError,
    SyncService,
)

from tests.conftest import GAME_ID, read_save, register_game, write_save


class Device:
    """
    A SaveCloud installation on one machine.
    """

    def __init__(
        self,
        monkeypatch,
        home,
        remote,
        working_save,
    ) -> None:

        self.monkeypatch = monkeypatch
        self.home = home
        self.remote = remote
        self.working_save = working_save

        self.activate()

        SaveCloudLibrary.initialize()

        ConfigurationService.save(
            InstallationConfig(
                storage_backend="local",
                storage_root=remote,
            )
        )

        self.device_id = SaveCloudLibrary.device_id()

    def activate(self) -> None:
        """
        Make this the installation subsequent calls operate on.
        """

        self.monkeypatch.setenv("SAVECLOUD_HOME", str(self.home))

    def game(self):
        """
        Load the shared game from this device's registry.
        """

        return RegistryService.load_game(GAME_ID)

    def sync(
        self,
        resolution: ConflictResolution = ConflictResolution.ABORT,
    ) -> SyncAction:
        """
        Synchronize the shared game.
        """

        return SyncService.sync(self.game(), resolution)

    def save_contents(self) -> str:
        """
        Return what the game would read on this device.
        """

        return read_save(self.working_save)

    def play(self, contents: str) -> None:
        """
        Simulate a play session that writes new save data.
        """

        write_save(self.working_save, contents)


@pytest.fixture
def desktop(monkeypatch, tmp_path):
    """
    The device where the game is first registered.
    """

    device = Device(
        monkeypatch,
        home=tmp_path / "desktop-home",
        remote=tmp_path / "shared-remote",
        working_save=tmp_path / "desktop-save",
    )

    write_save(device.working_save, "chapter one")

    register_game(device.working_save)

    return device


@pytest.fixture
def deck(monkeypatch, tmp_path):
    """
    A second device that has never seen the game.
    """

    return Device(
        monkeypatch,
        home=tmp_path / "deck-home",
        remote=tmp_path / "shared-remote",
        working_save=tmp_path / "deck-save",
    )


def pair_game(device: Device) -> None:
    """
    Adopt the shared game onto a device.

    Mirrors what the `pair` command does: pull the game down, then
    supply the only thing that cannot be synchronized - where the save
    lives on this machine.
    """

    device.activate()

    SyncService.adopt(GAME_ID)

    DeviceService.create_profile(
        DeviceProfile(
            device_id=device.device_id,
            device_name=SaveCloudLibrary.device_name(),
            game_id=GAME_ID,
            working_save_path=device.working_save,
            launch_command="true",
        )
    )

    SaveService.export_save(device.game(), DeviceService.load_profile(
        device.device_id,
        GAME_ID,
    ))


def test_devices_have_distinct_identities(desktop, deck):

    assert desktop.device_id != deck.device_id


def test_pairing_adopts_the_game_without_re_registering(desktop, deck):

    desktop.activate()
    desktop.sync()

    deck.activate()

    assert not RegistryService.exists(GAME_ID)

    pair_game(deck)

    assert RegistryService.exists(GAME_ID)

    #
    # Configuration travelled with the game.
    #

    assert deck.game().manifest.display_name == "Test Game"

    #
    # And so did the save.
    #

    assert deck.save_contents() == "chapter one"


def test_progress_flows_from_desktop_to_deck(desktop, deck):

    desktop.activate()
    desktop.sync()

    pair_game(deck)

    desktop.activate()
    desktop.play("chapter two")
    assert desktop.sync() is SyncAction.UPLOAD

    deck.activate()
    assert deck.sync() is SyncAction.DOWNLOAD

    assert deck.save_contents() == "chapter two"


def test_progress_flows_back_from_deck_to_desktop(desktop, deck):

    desktop.activate()
    desktop.sync()

    pair_game(deck)

    #
    # Play on the Deck.
    #

    deck.activate()
    deck.play("chapter three, on the couch")
    assert deck.sync() is SyncAction.UPLOAD

    #
    # Return to the desktop.
    #

    desktop.activate()
    assert desktop.sync() is SyncAction.DOWNLOAD

    assert desktop.save_contents() == "chapter three, on the couch"


def test_a_full_round_trip_leaves_both_devices_in_agreement(desktop, deck):

    desktop.activate()
    desktop.sync()

    pair_game(deck)

    for turn, contents in enumerate(
        [
            "desktop session one",
            "deck session one",
            "desktop session two",
            "deck session two",
        ]
    ):
        device = desktop if turn % 2 == 0 else deck

        device.activate()
        device.sync()
        device.play(contents)
        device.sync()

    desktop.activate()
    desktop.sync()

    assert desktop.save_contents() == "deck session two"

    deck.activate()
    deck.sync()

    assert deck.save_contents() == "deck session two"


def test_playing_on_both_devices_without_syncing_is_a_conflict(desktop, deck):

    desktop.activate()
    desktop.sync()

    pair_game(deck)

    deck.activate()
    deck.sync()

    #
    # Both devices play from the same starting point without
    # synchronizing in between.
    #

    desktop.activate()
    desktop.play("desktop ending")
    desktop.sync()

    deck.activate()
    deck.play("deck ending")

    with pytest.raises(SyncConflictError):
        deck.sync()

    #
    # Neither save was destroyed.
    #

    assert deck.save_contents() == "deck ending"

    desktop.activate()

    assert desktop.save_contents() == "desktop ending"


def test_resolving_a_conflict_keeps_the_losing_save_recoverable(desktop, deck):

    desktop.activate()
    desktop.sync()

    pair_game(deck)

    deck.activate()
    deck.sync()

    desktop.activate()
    desktop.play("desktop ending")
    desktop.sync()

    deck.activate()
    deck.play("deck ending")

    assert deck.sync(ConflictResolution.LOCAL) is SyncAction.UPLOAD

    assert deck.save_contents() == "deck ending"

    #
    # The desktop's save survives in the Deck's version history.
    #

    game = deck.game()

    archived = [
        read_save(SaveCloudLibrary.version_directory(GAME_ID, version))
        for version in SaveService.list_versions(game)
    ]

    assert "desktop ending" in archived


def test_a_device_profile_never_travels(desktop, deck):
    """
    Save paths differ per machine and must stay local.
    """

    desktop.activate()
    desktop.sync()

    pair_game(deck)

    deck_profile = DeviceService.load_profile(deck.device_id, GAME_ID)

    assert deck_profile.working_save_path == deck.working_save

    desktop.activate()
    desktop.sync()

    desktop_profile = DeviceService.load_profile(desktop.device_id, GAME_ID)

    assert desktop_profile.working_save_path == desktop.working_save

    #
    # Neither device can see the other's profile.
    #

    assert not DeviceService.exists(deck.device_id, GAME_ID)


def test_version_history_is_shared_between_devices(desktop, deck):

    desktop.activate()
    desktop.sync()

    desktop.play("chapter two")
    desktop.sync()

    pair_game(deck)

    deck.activate()

    #
    # The Deck inherits the history built on the desktop.
    #

    assert len(SaveService.list_versions(deck.game())) >= 2
