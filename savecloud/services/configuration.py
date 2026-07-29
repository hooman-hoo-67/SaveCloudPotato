"""
Installation configuration service.

ConfigurationService owns config.json. It is the only component that
reads or writes installation-wide settings.

Commands and services must never touch config.json directly.
"""

from __future__ import annotations

import json

from savecloud.config.constants import config_path, savecloud_home
from savecloud.models.installation_config import InstallationConfig


class ConfigurationService:
    """
    Load and persist installation-wide configuration.
    """

    @staticmethod
    def path():
        """
        Return the configuration file path.
        """

        return config_path()

    @staticmethod
    def exists() -> bool:
        """
        Return True if a configuration file exists.
        """

        return config_path().exists()

    @staticmethod
    def default() -> InstallationConfig:
        """
        Return the default configuration.
        """

        return InstallationConfig()

    @staticmethod
    def save(
        config: InstallationConfig,
    ) -> None:
        """
        Write the configuration to disk.
        """

        savecloud_home().mkdir(
            parents=True,
            exist_ok=True,
        )

        with config_path().open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                config.to_dict(),
                file,
                indent=4,
            )

    @staticmethod
    def load() -> InstallationConfig:
        """
        Load the configuration.

        A missing or unreadable configuration falls back to the
        defaults rather than raising, so that SaveCloud keeps working
        on a partially initialized installation.
        """

        path = config_path()

        if not path.exists():
            return ConfigurationService.default()

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                return InstallationConfig.from_dict(
                    json.load(file),
                )

        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return ConfigurationService.default()

    @staticmethod
    def initialize() -> InstallationConfig:
        """
        Create the configuration file if it does not exist.

        Returns the configuration currently in effect.
        """

        if ConfigurationService.exists():
            return ConfigurationService.load()

        config = ConfigurationService.default()

        ConfigurationService.save(config)

        return config

    @staticmethod
    def set_backend(
        name: str,
    ) -> InstallationConfig:
        """
        Change the active storage backend.
        """

        from savecloud.storage import StorageRegistry

        if not StorageRegistry.exists(name):
            raise ValueError(
                f'Unknown storage backend: "{name}".',
            )

        config = ConfigurationService.load()

        config.storage_backend = name.lower()

        ConfigurationService.save(config)

        return config

    @staticmethod
    def set_retention(
        count: int,
    ) -> InstallationConfig:
        """
        Change how many historical versions are kept per game.

        Zero keeps every version.
        """

        if count < 0:
            raise ValueError("Version retention cannot be negative.")

        config = ConfigurationService.load()

        config.version_retention = count

        ConfigurationService.save(config)

        return config

    @staticmethod
    def set_root(
        root,
    ) -> InstallationConfig:
        """
        Change the storage root directory.
        """

        from pathlib import Path

        config = ConfigurationService.load()

        config.storage_root = Path(root).expanduser()

        ConfigurationService.save(config)

        return config
