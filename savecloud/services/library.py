"""
Filesystem management for the SaveCloud Library.

The SaveCloud Library is the canonical storage location for all managed
game saves. This module is responsible for creating, validating, and
maintaining the library's filesystem structure.
"""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from savecloud.config.constants import (
    DIRECTORIES,
    INSTALL_METADATA,
    SAVECLOUD_HOME,
    SAVECLOUD_VERSION,
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
        Create the SaveCloud installation metadata.
        """

        metadata = {
            "schema_version": SCHEMA_VERSION,
            "savecloud_version": SAVECLOUD_VERSION,
            "device_id": str(uuid4()),
            "device_name": socket.gethostname(),
            "created_at": datetime.now(UTC).isoformat(),
        }

        with INSTALL_METADATA.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=4)

    @staticmethod
    def installation_metadata() -> dict:
        """
        Return the installation metadata.
        """

        with INSTALL_METADATA.open("r", encoding="utf-8") as file:
            return json.load(file)

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
            metadata = SaveCloudLibrary.installation_metadata()

            required_fields = (
                "schema_version",
                "savecloud_version",
                "device_id",
                "device_name",
                "created_at",
            )

            if not all(field in metadata for field in required_fields):
                return False

            return metadata["schema_version"] == SCHEMA_VERSION

        except (json.JSONDecodeError, OSError, KeyError):
            return False
