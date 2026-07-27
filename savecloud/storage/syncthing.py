"""
Syncthing storage backend.

Syncthing presents itself as an ordinary directory, so transfer works
exactly as it does for local storage. What differs is availability and
failure modes:

- The storage root must actually be a folder Syncthing manages,
  otherwise saves would be written somewhere that never replicates.
- Syncthing resolves simultaneous edits by preserving both sides as
  ``*.sync-conflict-*`` files. Those are surfaced rather than silently
  synchronized into a save.
"""

from __future__ import annotations

from pathlib import Path

from savecloud.services.configuration import ConfigurationService
from savecloud.storage.filesystem import FilesystemStorageBackend

#
# Marker directory Syncthing places inside every folder it manages.
#

FOLDER_MARKER = ".stfolder"

CONFLICT_PATTERN = "*.sync-conflict-*"


class SyncthingStorageBackend(FilesystemStorageBackend):
    """
    Synchronize the library through a Syncthing folder.
    """

    @staticmethod
    def display_name() -> str:
        """
        Human-readable backend name.
        """

        return "Syncthing"

    @classmethod
    def storage_root(cls) -> Path:
        """
        Return the configured storage root.
        """

        return ConfigurationService.load().storage_root

    @classmethod
    def marker_path(cls) -> Path:
        """
        Return the expected Syncthing folder marker.
        """

        return cls.storage_root() / FOLDER_MARKER

    @classmethod
    def available(cls) -> bool:
        """
        Return True if the storage root is a Syncthing folder.

        Unlike the local backend, this does not create the root. A
        missing root means Syncthing is not sharing it, and creating it
        would produce a directory that never replicates.
        """

        root = cls.storage_root()

        if not root.is_dir():
            return False

        return cls.marker_path().exists()

    @classmethod
    def unavailable_reason(cls) -> str:
        """
        Explain why the Syncthing folder is unusable.
        """

        root = cls.storage_root()

        if not root.is_dir():
            return f"Syncthing folder does not exist: {root}"

        return (
            f"{root} is not a Syncthing folder "
            f"(no {FOLDER_MARKER} marker). Share it in Syncthing first, "
            f"or switch to the local backend."
        )

    @classmethod
    def conflicts(
        cls,
        game_id: str | None = None,
    ) -> list[Path]:
        """
        Return Syncthing conflict files.

        Parameters
        ----------
        game_id
            Restrict the search to one game. When omitted, the whole
            storage root is searched.
        """

        root = cls.game_directory(game_id) if game_id else cls.storage_root()

        if not root.exists():
            return []

        return sorted(
            path for path in root.rglob(CONFLICT_PATTERN) if path.is_file()
        )
