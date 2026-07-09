"""
Adapter for the Eden Nintendo Switch emulator.
"""

from __future__ import annotations

from pathlib import Path


class EdenAdapter:
    """
    SaveCloud adapter for the Eden emulator.
    """

    @staticmethod
    def display_name() -> str:
        """
        Return the adapter's display name.
        """

        return "Eden"

    @staticmethod
    def validate_save(
        path: Path,
    ) -> bool:
        """
        Validate an Eden save directory.
        """

        return (
            path.exists()
            and path.is_dir()
        )

    @staticmethod
    def locate_save() -> Path | None:
        """
        Attempt to locate the default Eden save
        directory.

        Automatic discovery is not implemented yet.
        """

        return None

    @staticmethod
    def save_root() -> Path:
        """
        Return the Eden save root directory.
        """

        return (
            Path.home()
            / ".local"
            / "share"
            / "eden"
            / "nand"
            / "user"
            / "save"
        )

    @staticmethod
    def find_users() -> list[Path]:
        """
        Return a list of Eden user directories.
        """

        users_root = (
            EdenAdapter.save_root()
            / "0000000000000000"
        )

        if not users_root.exists():
            return []

        return [
            path
            for path in users_root.iterdir()
            if path.is_dir()
        ]

    @staticmethod
    def find_save(
        title_id: str,
    ) -> Path | None:
        """
        Attempt to locate a save directory for the
        given title ID.
        """

        for user in EdenAdapter.find_users():
            candidate = user / title_id

            if (
                candidate.exists()
                and candidate.is_dir()
            ):
                return candidate

        return None