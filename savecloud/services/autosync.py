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

import subprocess

from savecloud.launchers import LauncherRegistry
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


class UntrackableLaunchError(RuntimeError):
    """
    Raised when a launcher cannot report that the game has exited.
    """

    def __init__(
        self,
        game_id: str,
        launcher: str,
    ) -> None:

        super().__init__(
            f'The "{launcher}" launcher hands the game off to another '
            f"program and cannot tell when it exits, so the save after "
            f"the session would never be captured.",
        )

        self.game_id = game_id
        self.launcher = launcher


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

        #
        # Refuse before synchronizing. A launcher that cannot report
        # the game's exit would have this method capture the save from
        # before the session and mark it synchronized, quietly losing
        # everything played.
        #

        launcher = LauncherRegistry.get(profile.launcher)

        if launcher is not None and not launcher.tracks_process_exit():
            raise UntrackableLaunchError(game_id, profile.launcher)

        result = PlayResult(exit_code=0)

        #
        # Bring this device up to date before playing.
        #

        AutoSyncService.before_launch(game, resolution, result)

        game.runtime.mark_running()

        RegistryService.update_runtime(game)

        process = LaunchService.launch(profile)

        exit_code = LaunchService.wait(process)

        AutoSyncService.after_exit(game, exit_code, result)

        return result

    @staticmethod
    def wrap(
        game: Game,
        argv: list[str],
        resolution: ConflictResolution = ConflictResolution.ABORT,
    ) -> PlayResult:
        """
        Run a command supplied by something else, around a sync.

        Used when Steam - or any launcher - starts SaveCloud and hands
        it the real command to run. The process tree is the right way
        round: the game is this process's child, so its exit is
        observable and the save can be captured afterwards.

        No launcher is consulted. The question a launcher answers, "how
        is this game started", has already been answered by the caller.

        Parameters
        ----------
        game
            Registered game.
        argv
            The command to run, already split into arguments.
        resolution
            How to resolve a conflict detected before launch.

        Raises
        ------
        SyncConflictError
            If both sides changed and ``resolution`` is ABORT. The game
            is not started.
        """

        if not argv:
            raise ValueError("No command was supplied to run.")

        result = PlayResult(exit_code=0)

        AutoSyncService.before_launch(game, resolution, result)

        game.runtime.mark_running()

        RegistryService.update_runtime(game)

        process = subprocess.Popen(argv)

        exit_code = process.wait()

        AutoSyncService.after_exit(game, exit_code, result)

        return result

    # ------------------------------------------------------------------
    # Shared lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def before_launch(
        game: Game,
        resolution: ConflictResolution,
        result: PlayResult,
    ) -> None:
        """
        Bring this device up to date before the game starts.

        Failures here are recorded and tolerated: an unreachable
        backend must never stop someone playing. An unresolved conflict
        is the one exception, and propagates.
        """

        if not game.manifest.sync_enabled:
            return

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

    @staticmethod
    def after_exit(
        game: Game,
        exit_code: int,
        result: PlayResult,
    ) -> None:
        """
        Capture and publish the session once the game has exited.
        """

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

            return

        if not game.manifest.sync_enabled:
            return

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

            return

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
