"""
Filesystem management for the SaveCloud Library.

The SaveCloud Library is the canonical storage location for all managed
game saves. This module is responsible for creating, validating, and
maintaining the library's filesystem structure.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from savecloud.config.constants import (
    SAVECLOUD_HOME,
    DIRECTORIES,
    INSTALL_METADATA,
    SCHEMA_VERSION,
)


class SaveCloudLibrary:
    """
    Responsible for creating and validating the SaveCloud filesystem.
    """

    @staticmethod
    def exists() -> bool:
        """
        Return True if the SaveCloud root directory exists.
        """
        return SAVECLOUD_HOME.exists()

    @staticmethod
    def create_install_metadata() -> None:
        """
        Create the SaveCloud installation metadata file.
        """

        metadata = {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
        }

        with INSTALL_METADATA.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=4)

    @staticmethod
    def initialize() -> list[Path]:
        """
        Create the SaveCloud directory structure.

        Returns
        -------
        list[Path]
            Directories that were created.
        """

        created: list[Path] = []

        SAVECLOUD_HOME.mkdir(parents=True, exist_ok=True)

        for directory in DIRECTORIES:
            if not directory.exists():
                directory.mkdir(parents=True)
                created.append(directory)

        SaveCloudLibrary.create_install_metadata()

        return created

    @staticmethod
    def validate() -> bool:
        """
        Validate the SaveCloud installation.

        Returns
        -------
        bool
            True if the installation is valid.
        """

        if not SAVECLOUD_HOME.exists():
            return False

        if not INSTALL_METADATA.exists():
            return False

        if not all(directory.exists() for directory in DIRECTORIES):
            return False

        try:
            with INSTALL_METADATA.open("r", encoding="utf-8") as file:
                metadata = json.load(file)

            return metadata.get("schema_version") == SCHEMA_VERSION

        except (json.JSONDecodeError, OSError, KeyError):
            return False
