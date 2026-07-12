"""
Filesystem management for the SaveCloud Library.

The SaveCloud Library is the canonical storage location for all managed
game saves. This module is responsible for creating, validating, and
maintaining the library's filesystem structure.
"""

from __future__ import annotations
from savecloud.models.game import Game
from savecloud.models.library_metadata import LibraryMetadata

import json
import socket
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from savecloud.config.constants import (
    DIRECTORIES,
    INSTALL_METADATA,
    LIBRARY_DIR,
    SAVECLOUD_HOME,
    SAVECLOUD_VERSION,
    SCHEMA_VERSION,
)


class SaveCloudLibrary:
    """
    Responsible for creating and validating the SaveCloud filesystem.
    """

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    @staticmethod
    def exists() -> bool:
        """Return True if the SaveCloud root directory exists."""
        return SAVECLOUD_HOME.exists()

    @staticmethod
    def create_install_metadata() -> None:
        """Create installation metadata."""

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
        """Return installation metadata."""

        with INSTALL_METADATA.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def device_id() -> str:
        """Return this installation's device ID."""
        return SaveCloudLibrary.installation_metadata()["device_id"]

    @staticmethod
    def device_name() -> str:
        """Return this installation's device name."""
        return SaveCloudLibrary.installation_metadata()["device_name"]

    @staticmethod
    def initialize() -> list[Path]:
        """
        Create the SaveCloud directory structure.
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

    # ------------------------------------------------------------------
    # Game Library
    # ------------------------------------------------------------------

    @staticmethod
    def library_directory(game_id: str) -> Path:
        """Return the library directory for a game."""
        return LIBRARY_DIR / game_id

    @staticmethod
    def current_directory(game_id: str) -> Path:
        """Return the current save directory."""
        return SaveCloudLibrary.library_directory(game_id) / "current"

    @staticmethod
    def versions_directory(game_id: str) -> Path:
        """Return the versions directory."""
        return SaveCloudLibrary.library_directory(game_id) / "versions"

    @staticmethod
    def version_directory(
        game_id: str,
        version: int,
    ) -> Path:
        """
        Return the directory for a specific save version.
        """

        return SaveCloudLibrary.versions_directory(game_id) / f"{version:06d}"

    @staticmethod
    def metadata_path(game_id: str) -> Path:
        """Return the metadata.json path."""
        return SaveCloudLibrary.library_directory(game_id) / "metadata.json"

    @staticmethod
    def load_library_metadata(
        game_id: str,
    ) -> LibraryMetadata:
        """
        Load a game's library metadata.
        """

        with SaveCloudLibrary.metadata_path(game_id).open(
            "r",
            encoding="utf-8",
        ) as file:
            return LibraryMetadata.from_dict(json.load(file))

    @staticmethod
    def save_library_metadata(
        game_id: str,
        metadata: LibraryMetadata,
    ) -> None:
        """
        Save a game's library metadata.
        """

        with SaveCloudLibrary.metadata_path(game_id).open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata.to_dict(),
                file,
                indent=4,
            )

    @staticmethod
    def create_game_library(game: Game) -> None:
        """
        Create the library structure for a game.
        """

        game_id = game.manifest.game_id

        SaveCloudLibrary.current_directory(game_id).mkdir(
            parents=True,
            exist_ok=True,
        )

        SaveCloudLibrary.versions_directory(game_id).mkdir(
            parents=True,
            exist_ok=True,
        )

        metadata = LibraryMetadata(
            current_version=game.runtime.current_version,
            latest_version=game.runtime.current_version,
            created_at=datetime.now(UTC).isoformat(),
            last_import=None,
            last_export=None,
        )

        with SaveCloudLibrary.metadata_path(game_id).open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata.to_dict(),
                file,
                indent=4,
            )

    @staticmethod
    def delete_game_library(game_id: str) -> None:
        """
        Delete an entire game library.
        """

        library = SaveCloudLibrary.library_directory(game_id)

        if library.exists():
            shutil.rmtree(library)
