"""
SaveCloud filesystem layout.

Pure path construction, with no filesystem access and no business
logic. Services and storage backends both need to address the same
directories; keeping the layout here means neither has to depend on the
other to do it.
"""

from __future__ import annotations

from pathlib import Path

from savecloud.config.constants import (
    device_dir,
    library_dir,
    registry_dir,
)

#
# Library
#


def game_library_directory(game_id: str) -> Path:
    """Return a game's library directory."""
    return library_dir() / game_id


def current_directory(game_id: str) -> Path:
    """Return a game's current save directory."""
    return game_library_directory(game_id) / "current"


def versions_directory(game_id: str) -> Path:
    """Return a game's version history directory."""
    return game_library_directory(game_id) / "versions"


def version_directory(
    game_id: str,
    version: int,
) -> Path:
    """Return the directory for one save version."""
    return versions_directory(game_id) / f"{version:06d}"


def library_metadata_path(game_id: str) -> Path:
    """Return a game's library metadata path."""
    return game_library_directory(game_id) / "metadata.json"


#
# Registry
#


def game_registry_directory(game_id: str) -> Path:
    """Return a game's registry directory."""
    return registry_dir() / game_id


def manifest_path(game_id: str) -> Path:
    """Return a game's manifest path."""
    return game_registry_directory(game_id) / "manifest.json"


def runtime_path(game_id: str) -> Path:
    """Return a game's runtime path."""
    return game_registry_directory(game_id) / "runtime.json"


#
# Device
#


def device_directory(device_id: str) -> Path:
    """Return a device's profile directory."""
    return device_dir() / device_id


def device_profile_path(
    device_id: str,
    game_id: str,
) -> Path:
    """Return the profile path for a game on a device."""
    return device_directory(device_id) / f"{game_id}.json"


#
# Version naming
#


def version_number(name: str) -> int:
    """
    Parse a version directory name into its number.
    """

    return int(name)


def version_name(version: int) -> str:
    """
    Format a version number as a directory name.
    """

    return f"{version:06d}"
