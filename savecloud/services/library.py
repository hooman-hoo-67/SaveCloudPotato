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

from savecloud.config import layout
from savecloud.config.constants import (
    SAVECLOUD_VERSION,
    SCHEMA_VERSION,
    directories,
    install_metadata_path,
    savecloud_home,
)
from savecloud.utils.atomic import write_json


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
        return savecloud_home().exists()

    @staticmethod
    def create_install_metadata() -> None:
        """
        Create installation metadata.

        Existing metadata is preserved. The device ID identifies this
        machine across every synchronized device, so regenerating it
        would orphan the device's history.
        """

        path = install_metadata_path()

        if path.exists():
            return

        metadata = {
            "schema_version": SCHEMA_VERSION,
            "savecloud_version": SAVECLOUD_VERSION,
            "device_id": str(uuid4()),
            "device_name": socket.gethostname(),
            "created_at": datetime.now(UTC).isoformat(),
        }

        write_json(path, metadata)

    @staticmethod
    def installation_metadata() -> dict:
        """Return installation metadata."""

        with install_metadata_path().open("r", encoding="utf-8") as file:
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

        savecloud_home().mkdir(parents=True, exist_ok=True)

        for directory in directories():
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

        if not savecloud_home().exists():
            return False

        if not install_metadata_path().exists():
            return False

        if not all(directory.exists() for directory in directories()):
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
        return layout.game_library_directory(game_id)

    @staticmethod
    def current_directory(game_id: str) -> Path:
        """Return the current save directory."""
        return layout.current_directory(game_id)

    @staticmethod
    def versions_directory(game_id: str) -> Path:
        """Return the versions directory."""
        return layout.versions_directory(game_id)

    @staticmethod
    def version_directory(
        game_id: str,
        version: int,
    ) -> Path:
        """
        Return the directory for a specific save version.
        """

        return layout.version_directory(game_id, version)

    @staticmethod
    def metadata_path(game_id: str) -> Path:
        """Return the metadata.json path."""
        return layout.library_metadata_path(game_id)

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

        write_json(
            SaveCloudLibrary.metadata_path(game_id),
            metadata.to_dict(),
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
    def ensure_game_library(
        game_id: str,
        current_version: int = 0,
    ) -> None:
        """
        Create a game's library structure if it is missing.

        Used when adopting a game that already exists remotely, where
        the library must exist before a download can populate it.
        Existing metadata is never overwritten.
        """

        SaveCloudLibrary.current_directory(game_id).mkdir(
            parents=True,
            exist_ok=True,
        )

        SaveCloudLibrary.versions_directory(game_id).mkdir(
            parents=True,
            exist_ok=True,
        )

        if SaveCloudLibrary.metadata_path(game_id).exists():
            return

        SaveCloudLibrary.save_library_metadata(
            game_id,
            LibraryMetadata(
                current_version=current_version,
                latest_version=current_version,
                created_at=datetime.now(UTC).isoformat(),
                last_import=None,
                last_export=None,
            ),
        )

    @staticmethod
    def delete_game_library(game_id: str) -> None:
        """
        Delete an entire game library.
        """

        library = SaveCloudLibrary.library_directory(game_id)

        if library.exists():
            shutil.rmtree(library)

    @staticmethod
    def mark_import(
        game_id: str,
    ) -> None:
        """
        Update the last import timestamp.
        """

        metadata = SaveCloudLibrary.load_library_metadata(
            game_id,
        )

        metadata.last_import = datetime.now(
            UTC,
        ).isoformat()

        SaveCloudLibrary.save_library_metadata(
            game_id,
            metadata,
        )

    @staticmethod
    def mark_export(
        game_id: str,
    ) -> None:
        """
        Update the last export timestamp.
        """

        metadata = SaveCloudLibrary.load_library_metadata(
            game_id,
        )

        metadata.last_export = datetime.now(
            UTC,
        ).isoformat()

        SaveCloudLibrary.save_library_metadata(
            game_id,
            metadata,
        )

    @staticmethod
    def set_current_version(
        game_id: str,
        version: int,
    ) -> None:
        """
        Set the current version.
        """

        metadata = SaveCloudLibrary.load_library_metadata(
            game_id,
        )

        metadata.current_version = version

        SaveCloudLibrary.save_library_metadata(
            game_id,
            metadata,
        )

    @staticmethod
    def prune_versions(
        game_id: str,
        keep: int,
    ) -> list[int]:
        """
        Delete all but the newest ``keep`` versions.

        Returns the version numbers that were removed.

        A retention of zero keeps everything, which is the escape hatch
        for anyone who would rather spend the disk than lose history.
        """

        if keep <= 0:
            return []

        versions_directory = SaveCloudLibrary.versions_directory(game_id)

        if not versions_directory.exists():
            return []

        existing: list[int] = []

        for directory in versions_directory.iterdir():

            if not directory.is_dir():
                continue

            try:
                existing.append(int(directory.name))

            except ValueError:
                continue

        #
        # The current save is not a version, so `keep` counts history
        # only: keep=2 leaves the two most recent snapshots.
        #

        doomed = sorted(existing, reverse=True)[keep:]

        for version in doomed:
            shutil.rmtree(
                SaveCloudLibrary.version_directory(game_id, version),
                ignore_errors=True,
            )

        return sorted(doomed)

    @staticmethod
    def retained_versions(
        game_id: str,
        keep: int,
    ) -> set[str]:
        """
        Return the version directory names retention would keep.

        Named rather than numbered, because storage backends compare
        against remote directory names.
        """

        versions_directory = SaveCloudLibrary.versions_directory(game_id)

        names: list[str] = []

        if versions_directory.exists():
            names = [
                directory.name
                for directory in versions_directory.iterdir()
                if directory.is_dir()
            ]

        if keep <= 0:
            return set(names)

        return set(sorted(names, reverse=True)[:keep])

    @staticmethod
    def reconcile_versions(
        game_id: str,
    ) -> int:
        """
        Raise the recorded latest version to match what is on disk.

        A download brings version directories this device's metadata
        never allocated. Reconciling keeps the metadata truthful.

        Returns
        -------
        int
            The latest version after reconciliation.
        """

        versions_directory = SaveCloudLibrary.versions_directory(game_id)

        highest = 0

        if versions_directory.exists():

            for directory in versions_directory.iterdir():

                if not directory.is_dir():
                    continue

                try:
                    highest = max(highest, int(directory.name))

                except ValueError:
                    continue

        metadata = SaveCloudLibrary.load_library_metadata(game_id)

        if highest <= metadata.latest_version:
            return metadata.latest_version

        metadata.latest_version = highest

        SaveCloudLibrary.save_library_metadata(game_id, metadata)

        return highest

    @staticmethod
    def increment_latest_version(
        game_id: str,
    ) -> int:
        """
        Increment the latest version number.

        Returns
        -------
        int
            The new version number.
        """

        metadata = SaveCloudLibrary.load_library_metadata(
            game_id,
        )

        metadata.latest_version += 1

        SaveCloudLibrary.save_library_metadata(
            game_id,
            metadata,
        )

        return metadata.latest_version
