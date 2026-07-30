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

import signal
import subprocess

from savecloud.launchers import LauncherRegistry
from savecloud.services import journal
from savecloud.services.locking import GameLock
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


#
# Signals that mean "stop now, please", as opposed to a crash. Steam's
# Stop button and Gaming Mode's Exit Game both terminate a game this
# way, so a session ended by one of these is an ordinary session and
# its save deserves publishing.
#

SHUTDOWN_SIGNALS = (signal.SIGTERM, signal.SIGINT)


def auto_sync_enabled(game: Game) -> bool:
    """
    Return whether this device synchronizes this game automatically.

    Two switches, deliberately. `sync_enabled` on the manifest travels
    with the game and means "this game is managed at all". `enabled` on
    the device profile stays here and means "this device takes part" -
    which is what lets a laptop on a metered connection stop uploading
    without changing anything for the desktop it shares saves with.

    A device with no profile for the game has nothing to say about it,
    so the manifest decides alone.
    """

    if not game.manifest.sync_enabled:
        return False

    device_id = SaveCloudLibrary.device_id()

    game_id = game.manifest.game_id

    if not DeviceService.exists(device_id, game_id):
        return True

    return DeviceService.load_profile(device_id, game_id).enabled


def _is_ordinary_exit(exit_code: int) -> bool:
    """
    Return whether an exit code describes a normal end to a session.

    `subprocess` reports a signal death as the negated signal number,
    so a game closed from Gaming Mode arrives here as -15 rather than
    0. Treating that as a crash would mean saves never publish on a
    Steam Deck, where it is the usual way to close a game.
    """

    if exit_code == 0:
        return True

    return -exit_code in {int(number) for number in SHUTDOWN_SIGNALS}


#
# The session path is the one with nowhere to print. Steam starts
# `wrap`, and anything it writes to a terminal that does not exist is
# the same as writing nothing.
#

log = journal.logger("session")


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
        # Held for the whole session. A sync starting midway through
        # could decide to download and publish a remote save into the
        # working directory - over the file the running game has open.
        #

        with GameLock.hold(game_id, "playing", long_lived=True):

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

        with GameLock.hold(
            game.manifest.game_id,
            "playing",
            long_lived=True,
        ):

            AutoSyncService.before_launch(game, resolution, result)

            game.runtime.mark_running()

            RegistryService.update_runtime(game)

            process = subprocess.Popen(argv)

            exit_code = AutoSyncService._wait_forwarding_signals(process)

            AutoSyncService.after_exit(game, exit_code, result)

        return result

    @staticmethod
    def _wait_forwarding_signals(
        process: subprocess.Popen,
    ) -> int:
        """
        Wait for the game, passing shutdown signals on to it.

        Steam terminates the process it launched, which is SaveCloud
        rather than the game. Python's default action would end this
        process immediately, so the save would never be captured -
        which is the whole reason the wrapper is in the way.

        Forwarding the signal instead lets the game shut down and flush
        its save, and leaves SaveCloud alive to capture it.
        """

        def forward(number, frame) -> None:

            try:
                process.send_signal(number)

            except ProcessLookupError:
                #
                # It exited between the signal and this handler.
                #
                pass

        previous = {}

        for number in SHUTDOWN_SIGNALS:

            try:
                previous[number] = signal.signal(number, forward)

            except (ValueError, OSError):
                #
                # Only the main thread of the main interpreter can
                # install handlers. Waiting unprotected is still
                # better than refusing to launch.
                #
                pass

        try:
            return process.wait()

        finally:

            for number, handler in previous.items():

                try:
                    signal.signal(number, handler)

                except (ValueError, OSError):
                    pass

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

        if not auto_sync_enabled(game):
            return

        try:
            result.pre_launch = SyncService.sync(game, resolution)

        except SyncConflictError:
            #
            # Never launch into an unresolved conflict.
            #

            log.warning("%s: unresolved conflict, refusing to launch",
                        game.manifest.game_id)

            raise

        except StorageUnavailableError as error:
            log.warning("%s: storage unavailable before launch: %s",
                        game.manifest.game_id, error)

            result.warnings.append(
                f"Storage unavailable, playing offline: {error}",
            )

        except Exception as error:
            log.warning("%s: pre-launch sync failed: %s",
                        game.manifest.game_id, error, exc_info=True)

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

        log.info(
            "%s: exited with %s (%s)",
            game.manifest.game_id,
            exit_code,
            "ordinary" if _is_ordinary_exit(exit_code) else "unexpected",
        )

        game.runtime.mark_exited(exit_code)

        RegistryService.update_runtime(game)

        if not auto_sync_enabled(game):
            return

        #
        # Capture the session into the library before involving the
        # backend at all. Storage may be unreachable; the save must be
        # preserved regardless.
        #
        # Captured whatever the exit code. A crash is exactly when the
        # session is least reproducible, so discarding it is the worst
        # available response - and the library is versioned, so a bad
        # capture is recoverable while a missing one is not.
        #

        try:
            SyncService.capture(game)

        except Exception as error:

            log.error("%s: could not capture the session: %s",
                      game.manifest.game_id, error, exc_info=True)

            result.warnings.append(
                f"Could not capture the save into the library: {error}",
            )

            return

        log.info("%s: session captured into the library",
                 game.manifest.game_id)

        #
        # An unusual exit is captured but not published, so a crashed
        # session cannot propagate to other devices unasked. It is
        # marked pending, so an explicit `savecloud sync` still sends
        # it once the player has decided the save is good.
        #

        if not _is_ordinary_exit(exit_code):

            log.warning("%s: unexpected exit, captured but not published",
                        game.manifest.game_id)

            game.runtime.mark_pending()

            game.runtime.last_error = f"Game exited with code {exit_code}"

            RegistryService.update_runtime(game)

            result.warnings.append(
                f"Game exited with code {exit_code}. The save was kept "
                f"locally but not uploaded; run `savecloud sync "
                f"{game.manifest.game_id}` to publish it.",
            )

            return

        #
        # Push it if storage is reachable.
        #

        try:
            SyncService.upload(game)

            result.uploaded = True

            log.info("%s: session uploaded", game.manifest.game_id)

        except Exception as error:

            #
            # The save is safe in the library either way. Mark it
            # pending so the next sync pushes it.
            #

            log.warning("%s: upload failed, save kept locally: %s",
                        game.manifest.game_id, error)

            game.runtime.mark_pending()

            RegistryService.update_runtime(game)

            result.warnings.append(
                f"Save kept locally, upload failed: {error}",
            )
