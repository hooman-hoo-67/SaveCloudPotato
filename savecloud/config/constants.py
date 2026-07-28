"""
SaveCloud filesystem locations.

Paths are resolved at call time rather than import time so that the
SaveCloud home directory can be relocated through the SAVECLOUD_HOME
environment variable. This keeps tests isolated from a developer's real
installation and allows a single process to target more than one
installation.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "savecloud"

# Current filesystem schema
SCHEMA_VERSION = 1
SAVECLOUD_VERSION = "0.1.0"

# Environment variable used to relocate the installation.
HOME_ENV_VAR = "SAVECLOUD_HOME"


def savecloud_home() -> Path:
    """
    Return the SaveCloud home directory.
    """

    override = os.environ.get(HOME_ENV_VAR)

    if override:
        return Path(override).expanduser()

    return Path(user_data_dir(APP_NAME))


def install_metadata_path() -> Path:
    """Return the installation metadata path."""
    return savecloud_home() / "savecloud.json"


def config_path() -> Path:
    """Return the installation configuration path."""
    return savecloud_home() / "config.json"


def library_dir() -> Path:
    """Return the canonical library directory."""
    return savecloud_home() / "library"


def registry_dir() -> Path:
    """Return the registry directory."""
    return savecloud_home() / "registry"


def device_dir() -> Path:
    """Return the device profile directory."""
    return savecloud_home() / "device"


def cache_dir() -> Path:
    """Return the cache directory."""
    return savecloud_home() / "cache"


def log_dir() -> Path:
    """Return the log directory."""
    return savecloud_home() / "logs"


def provider_dir() -> Path:
    """Return the provider configuration directory."""
    return savecloud_home() / "providers"


def directories() -> tuple[Path, ...]:
    """
    Return every directory created during initialization.
    """

    return (
        library_dir(),
        registry_dir(),
        device_dir(),
        cache_dir(),
        log_dir(),
        provider_dir(),
    )


def default_storage_root() -> Path:
    """
    Return the default local storage root.

    This is the location used by the local storage backend when the
    installation has not configured one explicitly.
    """

    return Path.home() / "SaveCloudRemote"
