"""
Synchronization service.

Coordinates the working save, the canonical library, and the configured
storage backend. It contains no provider-specific logic: which backend
is in use is resolved through the StorageRegistry, and how that backend
moves bytes is the backend's own concern.
"""

from __future__ import annotations

from enum import StrEnum

from savecloud.models.game import Game, GameRuntime
from savecloud.models.remote_state import RemoteState
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.storage import StorageRegistry
from savecloud.services import journal
from savecloud.storage.base import BaseStorageBackend


log = journal.logger("sync")


class SyncAction(StrEnum):
    """
    What synchronization would do, or did, for a game.
    """

    UP_TO_DATE = "up-to-date"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    CONFLICT = "conflict"


class ConflictResolution(StrEnum):
    """
    How to resolve a detected conflict.
    """

    #
    # Fail rather than choose. The default: a conflict means two
    # devices have real, different progress, and only the user knows
    # which matters.
    #

    ABORT = "abort"

    #
    # Keep this device's save. The remote save is preserved as a
    # version before being replaced.
    #

    LOCAL = "local"

    #
    # Keep the remote save. This device's save is preserved as a
    # version before being replaced.
    #

    REMOTE = "remote"


class SyncConflictError(RuntimeError):
    """
    Raised when both sides changed and no resolution was supplied.
    """

    def __init__(
        self,
        game_id: str,
        local_checksum: str,
        remote_checksum: str,
    ) -> None:

        super().__init__(
            f'Save conflict for "{game_id}": this device and the remote '
            f"have both changed since the last synchronization.",
        )

        self.game_id = game_id
        self.local_checksum = local_checksum
        self.remote_checksum = remote_checksum


class StorageUnavailableError(RuntimeError):
    """
    Raised when the configured backend cannot be reached.
    """


class SyncService:
    """
    High-level synchronization workflows.
    """

    # ------------------------------------------------------------------
    # Backend resolution
    # ------------------------------------------------------------------

    @staticmethod
    def backend() -> type[BaseStorageBackend]:
        """
        Return the storage backend selected by the installation.
        """

        return StorageRegistry.resolve()

    @staticmethod
    def require_backend() -> type[BaseStorageBackend]:
        """
        Return the configured backend, ensuring it is usable.
        """

        backend = SyncService.backend()

        if not backend.available():

            reason = backend.unavailable_reason()

            log.warning("storage unavailable: %s", reason)

            raise StorageUnavailableError(reason)

        return backend

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    @staticmethod
    def local_checksum(game: Game) -> str:
        """
        Return the checksum representing this device's save.

        The working save wins when it exists: after a play session it
        holds progress the library has not captured yet.
        """

        game_id = game.manifest.game_id

        device_id = SaveCloudLibrary.device_id()

        if DeviceService.exists(device_id, game_id):

            profile = DeviceService.load_profile(device_id, game_id)

            if profile.working_save_path.exists():
                return SaveService.working_checksum(profile)

        return SaveService.checksum(game)

    @staticmethod
    def compare(
        game: Game,
        remote: RemoteState | None,
    ) -> SyncAction:
        """
        Decide what synchronization should do.

        Compares three checksums: this device's save, the backend's
        save, and the checksum recorded at the last successful
        synchronization. That last value is the common ancestor, and it
        is what separates "only one side moved" from a real conflict.
        """

        local = SyncService.local_checksum(game)

        #
        # Nothing stored remotely: this device defines the save.
        #

        if remote is None:
            return SyncAction.UPLOAD

        if local == remote.checksum:
            return SyncAction.UP_TO_DATE

        base = game.runtime.last_sync_checksum

        #
        # Without a common ancestor there is no way to tell which side
        # advanced. Refuse to guess.
        #

        if base is None:
            return SyncAction.CONFLICT

        local_changed = local != base
        remote_changed = remote.checksum != base

        if local_changed and remote_changed:
            return SyncAction.CONFLICT

        if local_changed:
            return SyncAction.UPLOAD

        if remote_changed:
            return SyncAction.DOWNLOAD

        #
        # Neither side moved from the ancestor, yet they differ. This
        # only happens if a checksum was recorded incorrectly; treat it
        # as a conflict rather than silently overwriting.
        #

        return SyncAction.CONFLICT

    @staticmethod
    def status(game: Game) -> SyncAction:
        """
        Report what synchronization would do, without changing anything.
        """

        backend = SyncService.backend()

        if not backend.available():
            raise StorageUnavailableError(
                backend.unavailable_reason(),
            )

        return SyncService.compare(
            game,
            backend.state(game.manifest.game_id),
        )

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    @staticmethod
    def capture(
        game: Game,
    ) -> bool:
        """
        Import the working save into the library and version it.

        Deliberately independent of any storage backend. The library is
        the source of truth whether or not storage can be reached, so a
        play session is never lost just because a backend is offline.

        Returns
        -------
        bool
            True if the working save differed and was captured.
        """

        game_id = game.manifest.game_id

        device_id = SaveCloudLibrary.device_id()

        if not DeviceService.exists(device_id, game_id):
            return False

        profile = DeviceService.load_profile(device_id, game_id)

        if not profile.working_save_path.exists():
            return False

        if not SaveService.has_changes(game, profile):
            return False

        SaveService.import_save(game, profile)

        SaveCloudLibrary.mark_import(game_id)

        #
        # A captured save earns a version immediately, so the contents
        # it replaced stay recoverable.
        #

        SaveService.create_version(game)

        return True

    @staticmethod
    def upload(
        game: Game,
    ) -> None:
        """
        Capture this device's save and push it to the backend.
        """

        game_id = game.manifest.game_id

        backend = SyncService.require_backend()

        try:
            SyncService.capture(game)

            #
            # Push whenever the library and the backend disagree.
            # Comparing checksums rather than tracking whether this
            # call changed anything means a previously failed upload
            # still gets retried.
            #

            local = SaveService.checksum(game)

            remote = backend.state(game_id)

            if remote is None or remote.checksum != local or not backend.exists(game_id):
                state = backend.upload(game)

            else:
                state = remote

            game.runtime.mark_synced(
                SaveCloudLibrary.device_id(),
                state.checksum,
            )

            RegistryService.update_runtime(game)

        except Exception as error:

            game.runtime.mark_error(str(error))

            RegistryService.update_runtime(game)

            raise

    @staticmethod
    def download(
        game: Game,
    ) -> None:
        """
        Pull the backend's save and publish it to the working save.
        """

        game_id = game.manifest.game_id

        backend = SyncService.require_backend()

        try:
            state = backend.download(game_id)

            #
            # The download brings version directories this device's
            # metadata has never seen.
            #

            SaveCloudLibrary.reconcile_versions(game_id)

            #
            # Reloading picks up the runtime that travelled with the
            # download, then this device's sync result is applied on
            # top of it.
            #

            runtime = SyncService._reload_runtime(game)

            if runtime is not None:
                game.runtime = runtime

            device_id = SaveCloudLibrary.device_id()

            if DeviceService.exists(device_id, game_id):

                profile = DeviceService.load_profile(device_id, game_id)

                SaveService.export_save(game, profile)

                SaveCloudLibrary.mark_export(game_id)

            game.runtime.mark_synced(
                device_id,
                state.checksum,
            )

            RegistryService.update_runtime(game)

        except Exception as error:

            game.runtime.mark_error(str(error))

            RegistryService.update_runtime(game)

            raise

    # ------------------------------------------------------------------
    # Synchronization
    # ------------------------------------------------------------------

    @staticmethod
    def sync(
        game: Game,
        resolution: ConflictResolution = ConflictResolution.ABORT,
    ) -> SyncAction:
        """
        Synchronize a game with the configured backend.

        Parameters
        ----------
        game
            Registered game.
        resolution
            How to proceed if both sides changed.

        Returns
        -------
        SyncAction
            The action that was performed.

        Raises
        ------
        SyncConflictError
            If both sides changed and ``resolution`` is ABORT.
        """

        game_id = game.manifest.game_id

        backend = SyncService.require_backend()

        remote = backend.state(game_id)

        action = SyncService.compare(game, remote)

        log.info("%s: comparison says %s", game_id, action.value)

        if action is SyncAction.CONFLICT:

            log.warning(
                "%s: both sides changed since %s",
                game_id,
                (game.runtime.last_sync_checksum or "no recorded ancestor")[:12],
            )

            return SyncService._resolve_conflict(
                game,
                remote,
                resolution,
            )

        if action is SyncAction.UPLOAD:
            SyncService.upload(game)
            return SyncAction.UPLOAD

        if action is SyncAction.DOWNLOAD:
            SyncService.download(game)
            return SyncAction.DOWNLOAD

        #
        # Already in agreement. Record the checksum so that a first
        # sync against a matching remote establishes the ancestor.
        #

        if remote is not None and game.runtime.last_sync_checksum is None:

            game.runtime.mark_synced(
                SaveCloudLibrary.device_id(),
                remote.checksum,
            )

            RegistryService.update_runtime(game)

        return SyncAction.UP_TO_DATE

    @staticmethod
    def sync_all(
        resolution: ConflictResolution = ConflictResolution.ABORT,
    ) -> dict[str, SyncAction | str]:
        """
        Synchronize every registered game.

        A failure on one game never stops the others; the error is
        recorded against that game and reporting continues.
        """

        from savecloud.services.autosync import auto_sync_enabled

        results: dict[str, SyncAction | str] = {}

        for game in RegistryService.list_games():

            #
            # Syncing everything is an automatic action, so a game this
            # device has opted out of is skipped. Naming the game
            # explicitly still synchronizes it.
            #

            if not auto_sync_enabled(game):
                continue

            try:
                results[game.manifest.game_id] = SyncService.sync(
                    game,
                    resolution,
                )

            except Exception as error:
                results[game.manifest.game_id] = str(error)

        return results

    # ------------------------------------------------------------------
    # Pairing
    # ------------------------------------------------------------------

    @staticmethod
    def remote_games() -> list[str]:
        """
        Return every game the backend holds.
        """

        return SyncService.require_backend().list_games()

    @staticmethod
    def prune_remote(keep: int | None = None) -> dict[str, list[str]]:
        """
        Enforce the retention window on the backend.

        Storage is trimmed during a push, so this covers the same gap
        `SaveService.apply_retention` covers locally: a window that
        changed while the saves did not.

        Returns the version names removed, keyed by game ID, omitting
        games that had nothing to remove.

        Raises
        ------
        StorageUnavailableError
            If the backend cannot be reached.
        """

        from savecloud.services.configuration import ConfigurationService

        if keep is None:
            keep = ConfigurationService.load().version_retention

        backend = SyncService.require_backend()

        removed: dict[str, list[str]] = {}

        for game_id in backend.list_games():

            pruned = backend.prune(game_id, keep)

            if pruned:
                removed[game_id] = pruned

        return removed

    @staticmethod
    def adopt(
        game_id: str,
    ) -> Game:
        """
        Adopt a game that exists remotely but not on this device.

        Downloads the registry documents and library contents so the
        game becomes registered locally. The caller is responsible for
        creating the DeviceProfile, since only this machine knows where
        its working save lives.
        """

        backend = SyncService.require_backend()

        if not backend.exists(game_id):
            raise FileNotFoundError(
                f'Storage holds no save for "{game_id}".',
            )

        SaveCloudLibrary.ensure_game_library(game_id)

        state = backend.download(game_id)

        #
        # The download brings the history built on other devices.
        #

        SaveCloudLibrary.reconcile_versions(game_id)

        if not RegistryService.exists(game_id):
            raise FileNotFoundError(
                f'Storage holds no registry data for "{game_id}". '
                f"Upload it from the device where it is registered first.",
            )

        game = RegistryService.load_game(game_id)

        game.runtime.mark_synced(
            SaveCloudLibrary.device_id(),
            state.checksum,
        )

        RegistryService.update_runtime(game)

        return game

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _reload_runtime(
        game: Game,
    ) -> GameRuntime | None:
        """
        Reload a runtime that arrived with a download.
        """

        try:
            return RegistryService.load_runtime(
                game.manifest.game_id,
            )

        except (OSError, KeyError, ValueError):
            return None

    @staticmethod
    def _resolve_conflict(
        game: Game,
        remote: RemoteState | None,
        resolution: ConflictResolution,
    ) -> SyncAction:
        """
        Apply a conflict resolution strategy.

        Whichever side loses is preserved as a version first, so a
        resolution never destroys progress.
        """

        game_id = game.manifest.game_id

        if resolution is ConflictResolution.ABORT:

            game.runtime.mark_conflict()

            RegistryService.update_runtime(game)

            raise SyncConflictError(
                game_id,
                SyncService.local_checksum(game),
                remote.checksum if remote else "",
            )

        if resolution is ConflictResolution.LOCAL:

            #
            # Preserve the remote save before overwriting it.
            #

            SyncService._archive_remote(game)

            #
            # Clearing the ancestor forces the upload path: this
            # device's save becomes the new truth.
            #

            game.runtime.last_sync_checksum = None

            SyncService.upload(game)

            return SyncAction.UPLOAD

        #
        # ConflictResolution.REMOTE
        #

        #
        # Preserve this device's save before overwriting it.
        #

        if SaveCloudLibrary.current_directory(game_id).exists():
            SaveService.create_version(game)

        SyncService.download(game)

        return SyncAction.DOWNLOAD

    @staticmethod
    def _archive_remote(
        game: Game,
    ) -> None:
        """
        Store the backend's save as a local version.

        The remote save is fetched into a scratch directory so that
        preserving it never disturbs the library or the registry.
        """

        from savecloud.utils.filesystem import remove_directory

        game_id = game.manifest.game_id

        backend = SyncService.require_backend()

        if not backend.exists(game_id):
            return

        staging = SaveCloudLibrary.library_directory(game_id) / ".conflict-remote"

        try:
            backend.fetch_current(game_id, staging)

            SaveService.create_version_from(game, staging)

        finally:
            remove_directory(staging)
