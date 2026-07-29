"""
What the interface is allowed to ask for.

Widgets never import a service. They ask this, which returns plain
data - so a view can be built and tested without an installation, and
so the questions the interface asks are visible in one file rather
than scattered across windows.

Readers return data and may raise. Actions return an `Outcome` and
never raise, because a window cannot catch an exception thrown on a
worker thread - and because a conflict is a question to ask rather
than a failure to report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from savecloud.models.diagnostic import Severity
from savecloud.services.autosync import auto_sync_enabled
from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.diagnostics import DiagnosticsService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import (
    ConflictResolution,
    StorageUnavailableError,
    SyncAction,
    SyncConflictError,
    SyncService,
)
from savecloud.storage import StorageRegistry


@dataclass(slots=True)
class Outcome:
    """
    What an action did, or why it did not.

    Actions return this rather than raising: a window cannot catch an
    exception thrown on a worker thread, and a conflict is not an
    error - it is a question the interface has to ask.
    """

    ok: bool
    message: str = ""
    game_id: str = ""
    action: str = ""

    #
    # Set when both sides changed. The interface must offer a choice
    # rather than report a failure.
    #

    conflict: bool = False


@dataclass(slots=True)
class GameRow:
    """
    One game, as the list shows it.
    """

    game_id: str
    display_name: str
    status: str
    pending_upload: bool
    auto_sync: bool
    paired: bool

    @property
    def summary(self) -> str:
        """
        The one-line state a person actually reads.
        """

        if not self.paired:
            return "not set up on this device"

        if self.pending_upload:
            return "waiting to upload"

        return self.status


@dataclass(slots=True)
class GameDetail:
    """
    Everything the detail pane shows about one game.
    """

    game_id: str
    display_name: str
    platform: str
    adapter: str
    launcher: str
    launch_command: str
    working_save_path: str
    status: str
    pending_upload: bool
    auto_sync: bool
    paired: bool
    latest_version: int
    restored_from: int
    last_sync: str
    last_device: str
    last_error: str
    versions: list[int] = field(default_factory=list)


@dataclass(slots=True)
class StorageSummary:
    """
    Where saves go, and whether that place can be reached.
    """

    backend: str
    display_name: str
    root: str
    retention: int
    available: bool
    reason: str


@dataclass(slots=True)
class Finding:
    """
    One diagnostic result, flattened for display.
    """

    severity: str
    title: str
    detail: str
    remedy: str

    @property
    def is_problem(self) -> bool:
        return self.severity in {"warning", "error"}


class GuiFacade:
    """
    Every question the interface may ask.
    """

    @staticmethod
    def device_name() -> str:
        """
        Name this installation calls itself.
        """

        return SaveCloudLibrary.device_name()

    @staticmethod
    def games() -> list[GameRow]:
        """
        Every registered game, in display order.
        """

        device_id = SaveCloudLibrary.device_id()

        rows = [
            GameRow(
                game_id=game.manifest.game_id,
                display_name=game.manifest.display_name,
                status=game.runtime.status.value,
                pending_upload=game.runtime.pending_upload,
                auto_sync=auto_sync_enabled(game),
                paired=DeviceService.exists(device_id, game.manifest.game_id),
            )
            for game in RegistryService.list_games()
        ]

        return sorted(rows, key=lambda row: row.display_name.lower())

    @staticmethod
    def detail(game_id: str) -> GameDetail:
        """
        One game in full.

        Raises
        ------
        KeyError
            If the game is not registered.
        """

        if not RegistryService.exists(game_id):
            raise KeyError(game_id)

        game = RegistryService.load_game(game_id)

        device_id = SaveCloudLibrary.device_id()

        paired = DeviceService.exists(device_id, game_id)

        profile = (
            DeviceService.load_profile(device_id, game_id) if paired else None
        )

        metadata = SaveCloudLibrary.load_library_metadata(game_id)

        return GameDetail(
            game_id=game_id,
            display_name=game.manifest.display_name,
            platform=game.manifest.platform.value,
            adapter=game.manifest.adapter,
            launcher="" if profile is None else profile.launcher,
            launch_command="" if profile is None else profile.launch_command,
            working_save_path=""
            if profile is None
            else str(profile.working_save_path),
            status=game.runtime.status.value,
            pending_upload=game.runtime.pending_upload,
            auto_sync=auto_sync_enabled(game),
            paired=paired,
            #
            # From the library rather than the runtime: the library is
            # the canonical owner of save data, and the runtime's copy
            # of these numbers is written once at registration and
            # never updated.
            #
            # `latest_version` is the newest snapshot. `current_version`
            # is not a synonym - it records which version the current
            # save was restored from, and is zero until a restore
            # happens, so showing it as "current version" would read
            # as nothing having been saved.
            #
            latest_version=metadata.latest_version,
            restored_from=metadata.current_version,
            last_sync=_moment(game.runtime.last_sync),
            last_device=_device(game.runtime.last_device, device_id),
            last_error=game.runtime.last_error or "",
            versions=SaveService.list_versions(game),
        )

    @staticmethod
    def storage() -> StorageSummary:
        """
        The configured backend and whether it answers.

        Reaching a cloud provider is a network call, so callers run
        this off the interface thread.
        """

        config = ConfigurationService.load()

        backend = StorageRegistry.get(config.storage_backend)

        if backend is None:
            return StorageSummary(
                backend=config.storage_backend,
                display_name=config.storage_backend,
                root=str(config.storage_root),
                retention=config.version_retention,
                available=False,
                reason=f'"{config.storage_backend}" is not a known backend.',
            )

        available = backend.available()

        return StorageSummary(
            backend=config.storage_backend,
            display_name=backend.display_name(),
            root=str(config.storage_root),
            retention=config.version_retention,
            available=available,
            reason="" if available else backend.unavailable_reason(),
        )

    @staticmethod
    def diagnostics() -> list[Finding]:
        """
        Everything `doctor` would report.
        """

        return [
            Finding(
                severity=finding.severity.value,
                title=finding.title,
                detail=finding.detail or "",
                remedy=finding.remedy or "",
            )
            for finding in DiagnosticsService.run()
        ]

    @staticmethod
    def library_path(game_id: str) -> Path:
        """
        Where a game's saves live on this machine.
        """

        return SaveCloudLibrary.library_directory(game_id)

    # ------------------------------------------------------------------
    # Actions
    #
    # Each returns an Outcome rather than raising. A window cannot
    # catch an exception thrown on a worker thread, and a conflict is
    # not an error anyway - it is a question, and the interface needs
    # enough structure to ask it.
    # ------------------------------------------------------------------

    @staticmethod
    def sync(
        game_id: str,
        resolution: str = "abort",
    ) -> Outcome:
        """
        Synchronize one game.

        Parameters
        ----------
        game_id
            Game to synchronize.
        resolution
            "abort", "keep-local", or "keep-remote".
        """

        choice = {
            "keep-local": ConflictResolution.LOCAL,
            "keep-remote": ConflictResolution.REMOTE,
        }.get(resolution, ConflictResolution.ABORT)

        try:
            action = SyncService.sync(
                RegistryService.load_game(game_id),
                choice,
            )

        except SyncConflictError:
            return Outcome(
                ok=False,
                conflict=True,
                game_id=game_id,
                message=(
                    "This device and the remote have both changed since "
                    "they last agreed."
                ),
            )

        except StorageUnavailableError as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(
            ok=True,
            game_id=game_id,
            message={
                SyncAction.UPLOAD: "Uploaded this device's save.",
                SyncAction.DOWNLOAD: "Downloaded the remote save.",
                SyncAction.UP_TO_DATE: "Already up to date.",
            }.get(action, "Synchronized."),
            action=action.value,
        )

    @staticmethod
    def sync_all() -> Outcome:
        """
        Synchronize every game this device takes part in.
        """

        try:
            results = SyncService.sync_all()

        except Exception as error:
            return Outcome(ok=False, message=str(error))

        if not results:
            return Outcome(ok=True, message="Nothing to synchronize.")

        failures = {
            game_id: outcome
            for game_id, outcome in results.items()
            if not isinstance(outcome, SyncAction)
        }

        if failures:
            return Outcome(
                ok=False,
                message="\n".join(
                    f"{game_id}: {reason}"
                    for game_id, reason in sorted(failures.items())
                ),
            )

        return Outcome(
            ok=True,
            message=f"Synchronized {len(results)} games.",
        )

    @staticmethod
    def snapshot(game_id: str) -> Outcome:
        """
        Capture the working save as a new version.
        """

        try:
            version = SaveService.create_version(
                RegistryService.load_game(game_id),
            )

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(
            ok=True,
            game_id=game_id,
            message=f"Created version {version}.",
        )

    @staticmethod
    def restore(game_id: str, version: int) -> Outcome:
        """
        Restore a version, preserving what it replaces.
        """

        try:
            SaveService.restore_version(
                RegistryService.load_game(game_id),
                version,
            )

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(
            ok=True,
            game_id=game_id,
            message=(
                f"Restored version {version}. What it replaced was kept "
                f"as a new version."
            ),
        )

    @staticmethod
    def set_auto_sync(game_id: str, enabled: bool) -> Outcome:
        """
        Choose whether this device synchronizes a game automatically.
        """

        device_id = SaveCloudLibrary.device_id()

        if not DeviceService.exists(device_id, game_id):
            return Outcome(
                ok=False,
                game_id=game_id,
                message="This game is not set up on this device.",
            )

        profile = DeviceService.load_profile(device_id, game_id)

        profile.enabled = enabled

        DeviceService.save_profile(profile)

        return Outcome(
            ok=True,
            game_id=game_id,
            message=(
                f"Automatic sync {'enabled' if enabled else 'disabled'} "
                f"on this device."
            ),
        )

    @staticmethod
    def play(game_id: str) -> Outcome:
        """
        Synchronize, launch, wait for exit, and capture the session.

        Blocking for as long as the game runs, so callers put it on a
        worker thread and leave it there.
        """

        from savecloud.services.autosync import (
            AutoSyncService,
            UntrackableLaunchError,
        )

        try:
            result = AutoSyncService.play(RegistryService.load_game(game_id))

        except SyncConflictError:
            return Outcome(
                ok=False,
                conflict=True,
                game_id=game_id,
                message=(
                    "This game has an unresolved conflict. Playing would "
                    "build new progress on top of it."
                ),
            )

        except UntrackableLaunchError as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        lines = [f"Game exited with code {result.exit_code}."]

        if result.uploaded:
            lines.append("The session was uploaded.")

        lines.extend(result.warnings)

        return Outcome(
            ok=result.exit_code == 0,
            game_id=game_id,
            message="\n".join(lines),
        )


def _device(recorded: str | None, here: str) -> str:
    """
    Name the device that last touched a game.

    Only this machine's own identifier can be resolved to a name -
    nothing synchronizes a directory of device names - so another
    device is shown by a short form of its ID rather than a UUID
    filling the pane.
    """

    if not recorded:
        return "-"

    if recorded == here:
        return "this device"

    return f"another device ({recorded[:8]})"


def _moment(value) -> str:
    """
    Render a timestamp for display, or a dash when there is none.
    """

    if value is None:
        return "never"

    return value.strftime("%Y-%m-%d %H:%M")


#
# Re-exported so views need not import the models package to compare a
# severity against anything.
#

SEVERITIES = tuple(severity.value for severity in Severity)
