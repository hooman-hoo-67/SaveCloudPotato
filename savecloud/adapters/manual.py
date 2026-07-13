"""
Manual save adapter.

Allows the user to specify any save directory manually.
"""

from __future__ import annotations

from pathlib import Path

from savecloud.adapters.base import BaseAdapter


class ManualAdapter(BaseAdapter):
    """
    Generic adapter for manually managed save folders.
    """

    @staticmethod
    def display_name() -> str:
        return "Manual"

    @staticmethod
    def identifier_name() -> str:
        return "Save Folder"

    @staticmethod
    def locate_save(
        identifier: str,
    ) -> Path | None:
        """
        Interpret the identifier as a filesystem path.
        """

        path = Path(identifier).expanduser()

        if path.exists() and path.is_dir():
            return path

        return None

    @staticmethod
    def validate_save(
        path: Path,
    ) -> bool:
        """
        Verify the supplied save directory exists.
        """

        return path.exists() and path.is_dir()

    @staticmethod
    def supports_auto_discovery() -> bool:
        return False
