"""
Save management service.

Responsible for importing, exporting, copying,
and versioning game save data.
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

from savecloud.services.library import SaveCloudLibrary
from savecloud.models.game import Game
from savecloud.models.device_profile import DeviceProfile
from savecloud.utils.hashing import hash_directory


class SaveService:
    """
    Service responsible for manipulating game save data.

    Responsibilities
    ----------------
    - Import saves into the SaveCloud library.
    - Export saves back to the working save location.
    - Create and restore save versions.
    - Validate save integrity.

    This service deliberately does not manage the library
    filesystem layout. That remains the responsibility of
    LibraryService.
    """

    @staticmethod
    def current_save(game: Game) -> Path:
        """
        Return the current managed save directory.
        """

        return SaveCloudLibrary.current_directory(
            game.manifest.game_id,
        )

    @staticmethod
    def import_save(
        game: Game,
        profile: DeviceProfile,
    ) -> None:
        """
        Import the current working save into the
        SaveCloud library.
        """

        source = profile.working_save_path

        if not source.exists():
            raise FileNotFoundError(f"Working save directory does not exist: {source}")

        if not source.is_dir():
            raise NotADirectoryError(f"Working save path is not a directory: {source}")

        destination = SaveService.current_save(game)

        if destination.exists():
            shutil.rmtree(destination)

        shutil.copytree(
            source,
            destination,
        )

    @staticmethod
    def export_save(
        game: Game,
        profile: DeviceProfile,
    ) -> None:
        """
        Export the managed save back to the
        working save location.
        """

        source = SaveService.current_save(game)

        if not source.exists():
            raise FileNotFoundError(f"Working save directory does not exist: {source}")

        if not source.is_dir():
            raise NotADirectoryError(f"Working save path is not a directory: {source}")

        destination = profile.working_save_path

        if destination.exists():
            shutil.rmtree(destination)

        shutil.copytree(
            source,
            destination,
        )

    @staticmethod
    def create_version(
        game: Game,
    ) -> int:
        """
        Create a new version from the
        current managed save.

        Returns
        -------
        int
            The version number that was created.
        """

        return SaveService.create_version_from(
            game,
            SaveService.current_save(game),
        )

    @staticmethod
    def create_version_from(
        game: Game,
        source: Path,
    ) -> int:
        """
        Create a new version from an arbitrary directory.

        Used when preserving a save that is not the current one, such
        as the losing side of a conflict.

        Returns
        -------
        int
            The version number that was created.
        """

        metadata = SaveCloudLibrary.load_library_metadata(
            game.manifest.game_id,
        )

        if not source.exists():
            raise FileNotFoundError(f"Save directory does not exist: {source}")

        if not source.is_dir():
            raise NotADirectoryError(f"Save path is not a directory: {source}")

        #
        # Allocate above whatever is actually on disk, not merely above
        # what the metadata has seen. A device that adopted a game
        # received version directories the metadata never allocated,
        # and versions are immutable.
        #

        existing = SaveService.list_versions(game)

        next_version = max(
            metadata.latest_version,
            max(existing) if existing else 0,
        ) + 1

        destination = SaveCloudLibrary.version_directory(
            game.manifest.game_id,
            next_version,
        )

        if destination.exists():
            raise FileExistsError(
                f"Version {next_version} already exists: {destination}",
            )

        shutil.copytree(
            source,
            destination,
        )

        metadata.latest_version = next_version

        SaveCloudLibrary.save_library_metadata(
            game.manifest.game_id,
            metadata,
        )

        return next_version

    @staticmethod
    def restore_version(
        game: Game,
        version: int,
    ) -> None:
        """
        Restore a previous version.

        The save being replaced is preserved as a new version first, so
        a restore is itself reversible and no history is ever lost.
        """

        if not SaveService.version_exists(
            game,
            version,
        ):
            raise FileNotFoundError(f"Version {version} does not exist.")

        source = SaveCloudLibrary.version_directory(
            game.manifest.game_id,
            version,
        )

        destination = SaveService.current_save(
            game,
        )

        #
        # Preserve what is about to be overwritten.
        #

        if destination.exists():
            SaveService.create_version(game)

        if destination.exists():
            shutil.rmtree(destination)

        shutil.copytree(
            source,
            destination,
        )

        metadata = SaveCloudLibrary.load_library_metadata(
            game.manifest.game_id,
        )

        metadata.current_version = version

        SaveCloudLibrary.save_library_metadata(
            game.manifest.game_id,
            metadata,
        )

    @staticmethod
    def list_versions(
        game: Game,
    ) -> list[int]:
        """
        Return all available save versions.
        """

        versions_directory = SaveCloudLibrary.versions_directory(
            game.manifest.game_id,
        )

        if not versions_directory.exists():
            return []

        versions: list[int] = []

        for directory in sorted(
            versions_directory.iterdir(),
        ):
            if not directory.is_dir():
                continue

            versions.append(int(directory.name))

        return versions

    @staticmethod
    def version_exists(
        game: Game,
        version: int,
    ) -> bool:
        """
        Return True if a save version exists.
        """

        return SaveCloudLibrary.version_directory(
            game.manifest.game_id,
            version,
        ).exists()

    @staticmethod
    def directories_equal(
        left: Path,
        right: Path,
    ) -> bool:
        """
        Recursively compare two directories.

        Returns
        -------
        bool
            True if both directory trees contain the
            same files with identical contents.
        """

        if not left.exists() or not right.exists():
            return False

        comparison = filecmp.dircmp(
            left,
            right,
        )

        #
        # Missing or extra files.
        #

        if comparison.left_only or comparison.right_only or comparison.funny_files:
            return False

        #
        # Compare common files.
        #

        matches, mismatches, errors = filecmp.cmpfiles(
            left,
            right,
            comparison.common_files,
            shallow=False,
        )

        if mismatches or errors:
            return False

        #
        # Recurse into subdirectories.
        #

        for directory in comparison.common_dirs:

            if not SaveService.directories_equal(
                left / directory,
                right / directory,
            ):
                return False

        return True

    @staticmethod
    def checksum(
        game: Game,
    ) -> str:
        """
        Return the checksum of the managed save.
        """

        return hash_directory(
            SaveService.current_save(game),
        )

    @staticmethod
    def working_checksum(
        profile: DeviceProfile,
    ) -> str:
        """
        Return the checksum of the working save.
        """

        return hash_directory(
            profile.working_save_path,
        )

    @staticmethod
    def has_changes(
        game: Game,
        profile: DeviceProfile,
    ) -> bool:
        """
        Determine whether the working save differs
        from the managed save.

        Returns
        -------
        bool
            True if changes are detected.
        """

        managed = SaveService.current_save(
            game,
        )

        working = profile.working_save_path

        #
        # A missing working save cannot be compared. Treat it as
        # unchanged so that synchronization never overwrites the
        # library with nothing.
        #

        if not working.exists():
            return False

        if not managed.exists():
            return True

        return SaveService.checksum(game) != SaveService.working_checksum(profile)
