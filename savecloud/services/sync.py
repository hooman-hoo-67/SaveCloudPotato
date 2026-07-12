"""
Synchronization service.

Responsible for orchestrating synchronization between the
working save, the SaveCloud library, and storage backends.
"""

from __future__ import annotations

from savecloud.models.game import Game
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.storage import get_backend


class SyncService:
    """
    High-level synchronization workflows.
    """

    @staticmethod
    def backend(game: Game):
        """
        Return the configured storage backend.
        """

        backend = get_backend(
            game.manifest.storage_backend,
        )

        if backend is None:
            raise RuntimeError(
                f'Unknown storage backend: "{game.manifest.storage_backend}".'
            )

        return backend

    @staticmethod
    def upload(
        game: Game,
    ) -> None:
        """
        Upload a game's managed save to the configured
        storage backend.
        """

        profile = DeviceService.load_profile(
            SaveCloudLibrary.device_id(),
            game.manifest.game_id,
        )

        backend = SyncService.backend(
            game,
        )

        try:
            #
            # Import working save into the managed library.
            #

            #
            # Determine whether anything has changed before
            # importing the working save.
            #

            changed = SaveService.has_changes(
                game,
                profile,
            )

            #
            # Import the latest working save.
            #

            SaveService.import_save(
                game,
                profile,
            )

            SaveCloudLibrary.mark_import(
                game.manifest.game_id,
            )

            #
            # Nothing changed.
            #

            if not changed:

                # If the remote is missing, upload the managed save
                # even though no content changes were detected.
                if not backend.exists(
                    game,
                ):

                    backend.upload(
                        game,
                    )

                    game.runtime.mark_synced(
                        SaveCloudLibrary.device_id(),
                    )

                    RegistryService.update_runtime(
                        game,
                    )

                    return

                game.runtime.mark_synced(
                    SaveCloudLibrary.device_id(),
                )

                RegistryService.update_runtime(
                    game,
                )

                return

            #
            # Create a snapshot before uploading.
            #

            SaveService.create_version(
                game,
            )

            #
            # Upload the managed save.
            #

            backend.upload(
                game,
            )

            #
            # Update runtime state.
            #

            game.runtime.mark_synced(
                SaveCloudLibrary.device_id(),
            )

            RegistryService.update_runtime(
                game,
            )

        except Exception as error:

            game.runtime.mark_error(
                str(error),
            )

            RegistryService.update_runtime(
                game,
            )

            raise

    @staticmethod
    def download(
        game: Game,
    ) -> None:
        """
        Download a managed save from the configured
        storage backend.
        """

        profile = DeviceService.load_profile(
            SaveCloudLibrary.device_id(),
            game.manifest.game_id,
        )

        backend = SyncService.backend(
            game,
        )

        try:
            #
            # Download the managed save from storage.
            #

            backend.download(
                game,
            )

            #
            # Export the managed save back to the
            # working] save directory.
            #

            SaveService.export_save(
                game,
                profile,
            )

            SaveCloudLibrary.mark_export(
                game.manifest.game_id,
            )

            #
            # Update runtime state.
            #

            game.runtime.mark_synced(
                SaveCloudLibrary.device_id(),
            )

            RegistryService.update_runtime(
                game,
            )

        except Exception as error:

            game.runtime.mark_error(
                str(error),
            )

            RegistryService.update_runtime(
                game,
            )

            raise

    @staticmethod
    def sync(
        game: Game,
    ) -> None:
        """
        Synchronize a game with its configured
        storage backend.
        """

        backend = SyncService.backend(
            game,
        )

        if not backend.exists(
            game,
        ):
            SyncService.upload(
                game,
            )
            return

        if game.runtime.pending_upload:
            SyncService.upload(
                game,
            )
            return

        SyncService.download(
            game,
        )
