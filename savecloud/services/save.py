"""
Save management service.

Responsible for importing, exporting, copying,
and versioning game save data.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from savecloud.services.library import SaveCloudLibrary
from savecloud.models.game import Game
from savecloud.models.device_profile import DeviceProfile


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
            raise FileNotFoundError(f"Managed save does not exist: {source}")

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
    ) -> None:
        """
        Create a new version from the
        current managed save.
        """

        metadata = SaveCloudLibrary.load_library_metadata(
            game.manifest.game_id,
        )

        next_version = metadata.latest_version + 1

        source = SaveService.current_save(
            game,
        )

        if not source.exists():
            raise FileNotFoundError(f"Managed save does not exist: {source}")

        destination = SaveCloudLibrary.version_directory(
            game.manifest.game_id,
            next_version,
        )

        if destination.exists():
            shutil.rmtree(destination)

        shutil.copytree(
            source,
            destination,
        )

        metadata.latest_version = next_version

        SaveCloudLibrary.save_library_metadata(
            game.manifest.game_id,
            metadata,
        )

    @staticmethod
    def restore_version(
        game: Game,
        version: int,
    ) -> None:
        """
        Restore a previous version.
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
