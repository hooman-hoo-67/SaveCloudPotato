"""
Tests for the adapter and launcher frameworks.
"""

from __future__ import annotations

from savecloud.adapters import AdapterRegistry
from savecloud.adapters.base import BaseAdapter
from savecloud.adapters.eden import EdenAdapter
from savecloud.adapters.manual import ManualAdapter
from savecloud.launchers import AppImageLauncher, LauncherRegistry, NativeLauncher
from savecloud.launchers.base import BaseLauncher
from savecloud.services.launch import LaunchService

from tests.conftest import GAME_ID

#
# Adapters
#


def test_registered_adapters():

    assert AdapterRegistry.names() == ["eden", "manual"]
    assert AdapterRegistry.get("manual") is ManualAdapter
    assert AdapterRegistry.get("eden") is EdenAdapter
    assert AdapterRegistry.get("dolphin") is None


def test_adapter_lookup_is_case_insensitive():

    assert AdapterRegistry.get("MANUAL") is ManualAdapter


def test_every_adapter_implements_the_interface():

    for name, adapter in AdapterRegistry.adapters().items():

        assert issubclass(adapter, BaseAdapter), name

        assert isinstance(adapter.display_name(), str)
        assert isinstance(adapter.identifier_name(), str)
        assert isinstance(adapter.supports_auto_discovery(), bool)


def test_manual_adapter_locates_an_existing_directory(tmp_path):

    assert ManualAdapter.locate_save(str(tmp_path)) == tmp_path


def test_manual_adapter_expands_a_home_relative_path(monkeypatch, tmp_path):

    monkeypatch.setenv("HOME", str(tmp_path))

    (tmp_path / "saves").mkdir()

    assert ManualAdapter.locate_save("~/saves") == tmp_path / "saves"


def test_manual_adapter_rejects_a_missing_directory(tmp_path):

    assert ManualAdapter.locate_save(str(tmp_path / "absent")) is None


def test_manual_adapter_rejects_a_file(tmp_path):

    target = tmp_path / "file.dat"

    target.write_text("data", encoding="utf-8")

    assert ManualAdapter.locate_save(str(target)) is None
    assert not ManualAdapter.validate_save(target)


def test_eden_adapter_finds_a_title(monkeypatch, tmp_path):

    save_root = tmp_path / ".local/share/eden/nand/user/save"

    title = save_root / "0000000000000000" / "user-one" / "0100ABCDEF"

    title.mkdir(parents=True)

    monkeypatch.setattr(
        EdenAdapter,
        "save_root",
        staticmethod(lambda: save_root),
    )

    assert EdenAdapter.locate_save("0100ABCDEF") == title


def test_eden_adapter_returns_none_for_an_unknown_title(monkeypatch, tmp_path):

    monkeypatch.setattr(
        EdenAdapter,
        "save_root",
        staticmethod(lambda: tmp_path / "absent"),
    )

    assert EdenAdapter.locate_save("0100ABCDEF") is None


def test_eden_adapter_advertises_auto_discovery():

    assert EdenAdapter.supports_auto_discovery()
    assert not ManualAdapter.supports_auto_discovery()


#
# Launchers
#


def test_registered_launchers():

    assert "native" in LauncherRegistry.names()
    assert "appimage" in LauncherRegistry.names()
    assert LauncherRegistry.get("native") is NativeLauncher


def test_every_launcher_implements_the_interface():

    for name, launcher in LauncherRegistry.launchers().items():

        assert issubclass(launcher, BaseLauncher), name

        assert isinstance(launcher.display_name(), str)


def test_native_launcher_validates_commands():

    assert NativeLauncher.validate("true")
    assert not NativeLauncher.validate("")
    assert not NativeLauncher.validate("   ")
    assert not NativeLauncher.validate("definitely-not-a-real-binary")


def test_native_launcher_runs_a_command():

    process = NativeLauncher.launch("true")

    assert process.wait() == 0


def test_appimage_launcher_requires_an_appimage(tmp_path):

    not_an_appimage = tmp_path / "game.sh"

    not_an_appimage.write_text("#!/bin/sh\n", encoding="utf-8")

    assert not AppImageLauncher.validate(str(not_an_appimage))

    appimage = tmp_path / "Game.AppImage"

    appimage.write_text("binary", encoding="utf-8")

    assert AppImageLauncher.validate(str(appimage))


def test_appimage_launcher_rejects_a_missing_file(tmp_path):

    assert not AppImageLauncher.validate(str(tmp_path / "Absent.AppImage"))


def test_a_new_launcher_needs_no_service_changes(registered_game, device_id):
    """
    The extension point LaunchService depends on.
    """

    launched = []

    class RecordingLauncher(BaseLauncher):

        @staticmethod
        def display_name() -> str:
            return "Recording"

        @staticmethod
        def validate(command: str) -> bool:
            return True

        @staticmethod
        def launch(command: str):
            launched.append(command)

            return NativeLauncher.launch("true")

    LauncherRegistry.register("recording", RecordingLauncher)

    try:
        from savecloud.services.device import DeviceService

        profile = DeviceService.load_profile(device_id, GAME_ID)

        profile.launcher = "recording"
        profile.launch_command = "anything at all"

        process = LaunchService.launch(profile)

        assert process.wait() == 0
        assert launched == ["anything at all"]

    finally:
        LauncherRegistry._LAUNCHERS.pop("recording", None)


def test_launch_rejects_an_unknown_launcher(registered_game, device_id):

    from savecloud.services.device import DeviceService

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "nonexistent"

    try:
        LaunchService.launch(profile)

        raise AssertionError("Expected an error for an unknown launcher.")

    except RuntimeError:
        pass


def test_launch_rejects_an_invalid_command(registered_game, device_id):

    from savecloud.services.device import DeviceService

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launch_command = "definitely-not-a-real-binary"

    try:
        LaunchService.launch(profile)

        raise AssertionError("Expected an error for an invalid command.")

    except ValueError:
        pass
