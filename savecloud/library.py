"""
Filesystem management for the SaveCloud Library.
"""

from pathlib import Path

from .constants import SAVECLOUD_HOME, DIRECTORIES


class SaveCloudLibrary:
    """
    Responsible for creating and validating the SaveCloud filesystem.
    """

    @staticmethod
    def exists() -> bool:
        """Return True if SaveCloud has already been initialized."""
        return SAVECLOUD_HOME.exists()

    @staticmethod
    def initialize() -> list[Path]:
        """
        Create the SaveCloud directory structure.

        Returns
        -------
        list[Path]
            A list of directories that were created.
        """

        created = []

        SAVECLOUD_HOME.mkdir(parents=True, exist_ok=True)

        for directory in DIRECTORIES:
            if not directory.exists():
                directory.mkdir(parents=True)
                created.append(directory)

        return created

    @staticmethod
    def validate() -> bool:
        """
        Validate that every required directory exists.
        """

        if not SAVECLOUD_HOME.exists():
            return False

        return all(directory.exists() for directory in DIRECTORIES)
