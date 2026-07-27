"""
Local storage backend.

Synchronizes the library against a plain directory on this machine.
Useful on its own for backups onto an external drive, and as the
building block other directory-shaped providers reuse.
"""

from __future__ import annotations

from pathlib import Path

from savecloud.services.configuration import ConfigurationService
from savecloud.storage.filesystem import FilesystemStorageBackend


class LocalStorageBackend(FilesystemStorageBackend):
    """
    Local folder storage backend.
    """

    @staticmethod
    def display_name() -> str:
        """
        Human-readable backend name.
        """

        return "Local"

    @classmethod
    def storage_root(cls) -> Path:
        """
        Return the configured storage root.
        """

        return ConfigurationService.load().storage_root
