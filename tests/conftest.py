"""
Shared test fixtures.

Every test runs against a SaveCloud installation created inside a
temporary directory. Nothing here touches a developer's real
installation, and no test depends on another test's leftovers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.models.installation_config import InstallationConfig
from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService

GAME_ID = "test-game"


@pytest.fixture(autouse=True)
def installation(tmp_path, monkeypatch):
    """
    Create an isolated SaveCloud installation.

    Applied automatically so that no test can accidentally run against
    the real installation.
    """

    home = tmp_path / "savecloud"

    monkeypatch.setenv("SAVECLOUD_HOME", str(home))

    SaveCloudLibrary.initialize()

    ConfigurationService.save(
        InstallationConfig(
            storage_backend="local",
            storage_root=tmp_path / "remote",
        )
    )

    return home


@pytest.fixture
def storage_root(tmp_path) -> Path:
    """
    Return the configured storage root.
    """

    return tmp_path / "remote"


@pytest.fixture
def working_save(tmp_path) -> Path:
    """
    Create a working save directory containing one file.
    """

    directory = tmp_path / "working"

    directory.mkdir(parents=True, exist_ok=True)

    (directory / "save.dat").write_text(
        "original",
        encoding="utf-8",
    )

    return directory


@pytest.fixture
def device_id() -> str:
    """
    Return this installation's device ID.
    """

    return SaveCloudLibrary.device_id()


def build_game(
    game_id: str = GAME_ID,
    adapter: str = "manual",
    sync_enabled: bool = True,
) -> Game:
    """
    Build an unregistered Game object.
    """

    return Game(
        manifest=GameManifest(
            game_id=game_id,
            display_name="Test Game",
            launch_type=LaunchType.MANUAL,
            platform=Platform.NATIVE,
            adapter=adapter,
            sync_enabled=sync_enabled,
        ),
        runtime=GameRuntime(),
    )


def register_game(
    working_save: Path,
    game_id: str = GAME_ID,
    launch_command: str = "true",
    sync_enabled: bool = True,
) -> Game:
    """
    Register a game with a device profile pointing at ``working_save``.
    """

    game = build_game(
        game_id=game_id,
        sync_enabled=sync_enabled,
    )

    RegistryService.create_registry(game)

    SaveCloudLibrary.create_game_library(game)

    DeviceService.create_profile(
        DeviceProfile(
            device_id=SaveCloudLibrary.device_id(),
            device_name=SaveCloudLibrary.device_name(),
            game_id=game_id,
            working_save_path=working_save,
            launch_command=launch_command,
        )
    )

    return game


@pytest.fixture
def registered_game(working_save) -> Game:
    """
    Register a game backed by the working save fixture.
    """

    return register_game(working_save)


def write_save(
    directory: Path,
    contents: str,
    name: str = "save.dat",
) -> None:
    """
    Write contents into a save directory.
    """

    directory.mkdir(parents=True, exist_ok=True)

    (directory / name).write_text(
        contents,
        encoding="utf-8",
    )


def read_save(
    directory: Path,
    name: str = "save.dat",
) -> str:
    """
    Read contents from a save directory.
    """

    return (directory / name).read_text(encoding="utf-8")
