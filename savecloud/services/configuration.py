"""
Installation configuration service.
"""

from __future__ import annotations

import json
from pathlib import Path

from savecloud.models.installation_config import InstallationConfig


class ConfigurationService:
    """
    Manage installation configuration.
    """

    CONFIG_FILE = Path.home() / ".local" / "share" / "savecloud" / "config.json"

    @staticmethod
    def exists() -> bool:
        """
        Return True if the configuration exists.
        """

        return ConfigurationService.CONFIG_FILE.exists()

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
        Save the installation configuration.
        """

        ConfigurationService.CONFIG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "storage_backend": config.storage_backend,
            "storage_root": str(
                config.storage_root,
            ),
        }

        with ConfigurationService.CONFIG_FILE.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=4,
            )

    @staticmethod
    def load() -> InstallationConfig:
        """
        Load the installation configuration.
        """

        if not ConfigurationService.exists():
            return ConfigurationService.default()

        with ConfigurationService.CONFIG_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file,
            )

        return InstallationConfig(
            storage_backend=data["storage_backend"],
            storage_root=Path(data["storage_root"]),
        )
