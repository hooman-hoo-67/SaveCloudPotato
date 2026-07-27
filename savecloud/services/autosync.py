"""
Automatic synchronization service.

Bridges launching and synchronization without either owning the other:

    synchronize
        ↓
    launch
        ↓
    wait
        ↓
    import
        ↓
    version
        ↓
    upload
"""

from __future__ import annotations

from dataclasses import dataclass, field

from savecloud.models.game import Game
from savecloud.services.device import DeviceService
from savecloud.services.launch import LaunchService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import (
    ConflictResolution,
    StorageUnavailableError,
    SyncAction,
    SyncConflictError,
    SyncService,
)


@dataclass(slots=True)
class PlayResult:
    """
    Outcome of a complete play session.
    """

    exit_code: int

    #
    # What synchronization did before the game launched.
    #

    pre_launch: SyncAction | None = None

    #
    # Whether the save was uploaded after the session.
    #

    uploaded: bool = False

    #
    # Non-fatal problems worth reporting to the user.
    #

    warnings: list[str] = field(default_factory=list)


class AutoSyncService:
    """
    High-level automatic synchronization workflows.
    """

    @staticmethod
    def play(
        game: Game,
        resolution: ConflictResolution = ConflictResolution.ABORT,
    ) -> PlayResult:
        """
        Play a managed game.

        Synchronization failures before launch never prevent play. A
        game that cannot reach its backend is still playable; the save
        is simply marked pending so it uploads at the next opportunity.

        Parameters
        ----------
        game
            Registered game.
        resolution
            How to resolve a conflict detected before launch.

        Returns
        -------
        PlayResult
            Exit code and a description of what synchronization did.

        Raises
        ------
        SyncConflictError
            If both sides changed and ``resolution`` is ABORT. The game
            is deliberately not launched, because playing would build
            new progress on top of an unresolved conflict.
        """

        game_id = game.manifest.game_id

        profile = DeviceService.load_profile(
            SaveCloudLibrary.device_id(),
            game_id,
        )

        result = PlayResult(exit_code=0)

        #
        # Bring this device up to date before playing.
        #

        if game.manifest.sync_enabled:

            try:
                result.pre_launch = SyncService.sync(game, resolution)

            except SyncConflictError:
                #
                # Never launch into an unresolved conflict.
                #
                raise

            except StorageUnavailableError as error:
                result.warnings.append(
                    f"Storage unavailable, playing offline: {error}",
                )

            except Exception as error:
                result.warnings.append(
                    f"Synchronization failed, playing offline: {error}",
                )

        #
        # Launch.
        #

        game.runtime.mark_running()

        RegistryService.update_runtime(game)

        process = LaunchService.launch(profile)

        exit_code = LaunchService.wait(process)

        result.exit_code = exit_code

        game.runtime.mark_exited(exit_code)

        RegistryService.update_runtime(game)

        #
        # A non-zero exit usually means the game crashed. Its save may
        # be half-written, so it is captured locally but not pushed.
        #

        if exit_code != 0:

            game.runtime.mark_error(
                f"Game exited with code {exit_code}",
            )

            RegistryService.update_runtime(game)

            return result

        if not game.manifest.sync_enabled:
            return result

        #
        # Capture the session into the library before involving the
        # backend at all. Storage may be unreachable; the save must be
        # preserved regardless.
        #

        try:
            SyncService.capture(game)

        except Exception as error:

            result.warnings.append(
                f"Could not capture the save into the library: {error}",
            )

            return result

        #
        # Push it if storage is reachable.
        #

        try:
            SyncService.upload(game)

            result.uploaded = True

        except Exception as error:

            #
            # The save is safe in the library either way. Mark it
            # pending so the next sync pushes it.
            #

            game.runtime.mark_pending()

            RegistryService.update_runtime(game)

            result.warnings.append(
                f"Save kept locally, upload failed: {error}",
            )

        return result
