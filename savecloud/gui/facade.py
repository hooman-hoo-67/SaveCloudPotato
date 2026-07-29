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

from savecloud.models.device_profile import DeviceProfile
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

    #
    # A single result the caller asked for - a located save path, for
    # instance. Named rather than typed, because an interface needs
    # one string far more often than it needs a schema.
    #

    value: str = ""


@dataclass(slots=True)
class AdapterChoice:
    """
    One adapter, as a form offers it.
    """

    name: str
    identifier_name: str
    identifier_is_path: bool


@dataclass(slots=True)
class Options:
    """
    The choices a form has to offer.

    Read from the registries rather than hard-coded, so a new adapter
    or launcher appears in the interface without it being changed.
    """

    adapters: list[AdapterChoice] = field(default_factory=list)
    launchers: list[str] = field(default_factory=list)
    launch_types: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    backends: list[tuple[str, str, bool]] = field(default_factory=list)


@dataclass(slots=True)
class SteamGame:
    """
    An installed Steam game, as a picker offers it.
    """

    app_id: str
    name: str

    @property
    def label(self) -> str:
        return f"{self.name}  ({self.app_id})"


@dataclass(slots=True)
class SaveCandidate:
    """
    A folder inside a Proton prefix that might hold the save.
    """

    path: str

    #
    # What to show. The absolute path runs to about ninety characters
    # of prefix nobody needs to read, and comparing two of them means
    # comparing their last few segments anyway.
    #

    relative: str

    modified: str
    empty: bool

    @property
    def label(self) -> str:

        if self.empty:
            return f"{self.relative}  (empty)"

        return f"{self.relative}  (written {self.modified})"


@dataclass(slots=True)
class Settings:
    """
    Installation-wide configuration, as a form shows it.
    """

    backend: str
    root: str
    retention: int
    needs_credentials: bool
    has_credentials: bool


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


    # ------------------------------------------------------------------
    # Registration and pairing
    # ------------------------------------------------------------------

    @staticmethod
    def options() -> Options:
        """
        Everything a form needs to populate its choices.
        """

        from savecloud.adapters import AdapterRegistry
        from savecloud.launchers import LauncherRegistry
        from savecloud.models.game import LaunchType, Platform

        adapters = []

        for name in AdapterRegistry.names():

            adapter = AdapterRegistry.get(name)

            if adapter is None:
                continue

            adapters.append(
                AdapterChoice(
                    name=name,
                    identifier_name=adapter.identifier_name(),
                    identifier_is_path=adapter.identifier_is_path(),
                )
            )

        backends = []

        for name in StorageRegistry.names():

            backend = StorageRegistry.get(name)

            backends.append(
                (
                    name,
                    name if backend is None else backend.display_name(),
                    bool(backend and backend.requires_setup()),
                )
            )

        return Options(
            adapters=adapters,
            launchers=list(LauncherRegistry.names()),
            launch_types=[member.value for member in LaunchType],
            platforms=[member.value for member in Platform],
            backends=backends,
        )

    # ------------------------------------------------------------------
    # Proton
    # ------------------------------------------------------------------

    @staticmethod
    def steam_games() -> list[SteamGame]:
        """
        Every Steam game installed on this device.

        Read from Steam's own library files, so nothing has to be
        running and no account is involved.
        """

        from savecloud.utils import steam

        games = [
            SteamGame(app_id=app_id, name=name)
            for app_id, name in steam.installed_apps().items()
        ]

        return sorted(games, key=lambda game: game.name.lower())

    @staticmethod
    def prefix_root(app_id: str) -> str:
        """
        The Windows user directory inside a game's Proton prefix.

        Empty when the game has no prefix yet, which is what a game
        that has never been launched looks like.
        """

        from savecloud.utils import steam

        directory = steam.prefix_user_directory(app_id)

        return "" if directory is None else str(directory)

    @staticmethod
    def save_candidates(app_id: str) -> list[SaveCandidate]:
        """
        Plausible save directories inside a game's prefix.

        Reported rather than chosen between. Windows games follow no
        convention, and silently synchronizing the wrong directory is
        worse than one more question - so each carries when it was last
        written, which is what actually distinguishes the save from the
        empty folders beside it.
        """

        from datetime import datetime

        from savecloud.utils import steam

        root = steam.prefix_user_directory(app_id)

        if root is None:
            return []

        candidates = []

        for path in steam.candidate_save_directories(app_id):

            written = steam.last_written(path)

            candidates.append(
                SaveCandidate(
                    path=str(path),
                    relative=str(path.relative_to(root)),
                    modified=(
                        ""
                        if not written
                        else datetime.fromtimestamp(written).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    ),
                    empty=not written,
                )
            )

        return candidates

    @staticmethod
    def steam_identifier(app_id: str, folder: str) -> Outcome:
        """
        Build the identifier that records a Proton save location.

        `<app-id>:<path relative to the prefix user directory>`, so the
        location survives Steam moving the prefix between libraries -
        which it does when a game is moved to another drive.
        """

        from savecloud.utils import steam

        app_id = app_id.strip()

        if not app_id:
            return Outcome(ok=False, message="Choose a game.")

        if not folder.strip():
            return Outcome(ok=False, message="Choose the save folder.")

        root = steam.prefix_user_directory(app_id)

        if root is None:
            return Outcome(
                ok=False,
                message=(
                    "That game has no Proton prefix yet. Launch it once "
                    "through Steam, then try again."
                ),
            )

        chosen = Path(folder.strip()).expanduser()

        if not chosen.is_dir():
            return Outcome(ok=False, message=f"{chosen} is not a directory.")

        try:
            relative = chosen.resolve().relative_to(root.resolve())

        except ValueError:
            return Outcome(
                ok=False,
                message=(
                    f"That folder is outside the game's prefix. Saves "
                    f"have to live under {root}."
                ),
            )

        #
        # The user directory itself is a valid answer for a game that
        # writes straight into it.
        #

        suffix = relative.as_posix()

        return Outcome(
            ok=True,
            value=app_id if suffix == "." else f"{app_id}:{suffix}",
        )

    @staticmethod
    def locate_save(adapter: str, identifier: str) -> Outcome:
        """
        Ask an adapter where a save lives, and whether it looks right.

        Separate from registering so a form can confirm the path
        before anything is written - the one part of registration that
        commonly fails, and the one worth showing before committing.
        """

        from savecloud.adapters import AdapterRegistry

        implementation = AdapterRegistry.get(adapter)

        if implementation is None:
            return Outcome(ok=False, message=f'Unknown adapter: "{adapter}".')

        if not identifier.strip():
            return Outcome(
                ok=False,
                message=f"{implementation.identifier_name()} is required.",
            )

        try:
            path = implementation.locate_save(identifier.strip())

        except Exception as error:
            return Outcome(ok=False, message=str(error))

        if path is None:
            return Outcome(
                ok=False,
                message=(
                    f"No save directory found for that "
                    f"{implementation.identifier_name().lower()}."
                ),
            )

        if not implementation.validate_save(path):
            return Outcome(
                ok=False,
                message=f"{path} does not look like a valid save directory.",
                value=str(path),
            )

        return Outcome(ok=True, message=str(path), value=str(path))

    @staticmethod
    def register(
        game_id: str,
        display_name: str,
        launch_type: str,
        platform: str,
        adapter: str,
        identifier: str,
        launcher: str,
        launch_command: str,
    ) -> Outcome:
        """
        Register a game on this device.
        """

        from savecloud.models.game import (
            Game,
            GameManifest,
            GameRuntime,
            LaunchType,
            Platform,
        )

        game_id = game_id.strip()

        if not game_id:
            return Outcome(ok=False, message="Game ID is required.")

        if not display_name.strip():
            return Outcome(ok=False, message="Display name is required.")

        if RegistryService.exists(game_id):
            return Outcome(
                ok=False,
                game_id=game_id,
                message=f'"{game_id}" is already registered.',
            )

        located = GuiFacade.locate_save(adapter, identifier)

        if not located.ok:
            return located

        try:
            game = Game(
                manifest=GameManifest(
                    game_id=game_id,
                    display_name=display_name.strip(),
                    launch_type=LaunchType(launch_type),
                    platform=Platform(platform),
                    adapter=adapter,
                ),
                runtime=GameRuntime(),
            )

            RegistryService.create_registry(game)

            SaveCloudLibrary.create_game_library(game)

            DeviceService.create_profile(
                DeviceProfile(
                    device_id=SaveCloudLibrary.device_id(),
                    device_name=SaveCloudLibrary.device_name(),
                    game_id=game_id,
                    working_save_path=Path(located.value),
                    launch_command=launch_command.strip(),
                    launcher=launcher,
                )
            )

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(
            ok=True,
            game_id=game_id,
            message=f"Registered {display_name.strip()}.",
        )

    @staticmethod
    def needs_installing() -> bool:
        """
        Return whether this build could be put on PATH and is not.

        False for a `pip install`, which already is.
        """

        from savecloud.services import integration

        return integration.is_packaged() and not integration.is_installed()

    @staticmethod
    def install() -> Outcome:
        """
        Put `savecloud` on PATH and add a menu entry.
        """

        from savecloud.services import integration

        result = integration.install()

        lines = [result.message] + result.warnings

        return Outcome(ok=result.ok, message="\n\n".join(lines))

    @staticmethod
    def steam_launch_options(game_id: str) -> str:
        """
        What to paste into a game's Launch Options in Steam.

        Steam replaces `%command%` with the whole real invocation,
        Proton included, so this one line works for a native game and
        a Windows one alike. It is the ordinary way to use SaveCloud -
        a launch command is only needed by `savecloud play`, which
        starts the game itself.

        The absolute path is used, because Steam is not started from a
        shell that has activated anything: a bare name resolves to
        nothing when SaveCloud lives in a virtual environment, and the
        game fails to start with no explanation.
        """

        from savecloud.utils.executable import launch_options

        return launch_options(game_id)

    @staticmethod
    def adapter_for(game_id: str) -> AdapterChoice | None:
        """
        The adapter a registered game uses, as a form offers it.

        Returns None for a game this device does not know about yet.
        """

        from savecloud.adapters import AdapterRegistry

        if not RegistryService.exists(game_id):
            return None

        name = RegistryService.load_manifest(game_id).adapter

        adapter = AdapterRegistry.get(name)

        if adapter is None:
            return None

        return AdapterChoice(
            name=name,
            identifier_name=adapter.identifier_name(),
            identifier_is_path=adapter.identifier_is_path(),
        )

    @staticmethod
    def pairable() -> Outcome:
        """
        Games storage holds that this device has not adopted.

        The message carries them newline-separated, because an Outcome
        is what every action returns and a list of names does not
        justify a second shape.
        """

        try:
            remote = SyncService.remote_games()

        except Exception as error:
            return Outcome(ok=False, message=str(error))

        device_id = SaveCloudLibrary.device_id()

        available = [
            game_id
            for game_id in remote
            if not DeviceService.exists(device_id, game_id)
        ]

        return Outcome(ok=True, message="\n".join(sorted(available)))

    @staticmethod
    def pair(
        game_id: str,
        identifier: str,
        launcher: str,
        launch_command: str,
    ) -> Outcome:
        """
        Adopt a game that exists in storage onto this device.

        The adapter comes with the downloaded manifest, so only the
        things that cannot be synchronized are asked for.
        """

        try:
            game = SyncService.adopt(game_id)

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        located = GuiFacade.locate_save(game.manifest.adapter, identifier)

        if not located.ok:
            return located

        try:
            DeviceService.create_profile(
                DeviceProfile(
                    device_id=SaveCloudLibrary.device_id(),
                    device_name=SaveCloudLibrary.device_name(),
                    game_id=game_id,
                    working_save_path=Path(located.value),
                    launch_command=launch_command.strip(),
                    launcher=launcher,
                )
            )

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(
            ok=True,
            game_id=game_id,
            message=f"Paired {game.manifest.display_name} with this device.",
        )

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    @staticmethod
    def update_game(
        game_id: str,
        display_name: str,
        sync_enabled: bool,
        backup_enabled: bool,
    ) -> Outcome:
        """
        Change a game's synchronized configuration.

        The manifest is frozen, so this replaces it rather than
        mutating it - configuration that changes rarely should not be
        quietly editable in memory.
        """

        from dataclasses import replace

        if not display_name.strip():
            return Outcome(ok=False, message="Display name is required.")

        try:
            manifest = RegistryService.load_manifest(game_id)

            RegistryService.save_registry_manifest(
                replace(
                    manifest,
                    display_name=display_name.strip(),
                    sync_enabled=sync_enabled,
                    backup_enabled=backup_enabled,
                )
            )

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(ok=True, game_id=game_id, message="Saved.")

    @staticmethod
    def update_profile(
        game_id: str,
        working_save_path: str,
        launcher: str,
        launch_command: str,
    ) -> Outcome:
        """
        Change how this device reaches a game.
        """

        device_id = SaveCloudLibrary.device_id()

        if not DeviceService.exists(device_id, game_id):
            return Outcome(
                ok=False,
                game_id=game_id,
                message="This game is not set up on this device.",
            )

        path = Path(working_save_path).expanduser()

        if not path.is_dir():
            return Outcome(
                ok=False,
                game_id=game_id,
                message=f"{path} is not a directory.",
            )

        profile = DeviceService.load_profile(device_id, game_id)

        profile.working_save_path = path

        profile.launcher = launcher

        profile.launch_command = launch_command.strip()

        DeviceService.save_profile(profile)

        return Outcome(ok=True, game_id=game_id, message="Saved.")

    @staticmethod
    def unregister(game_id: str) -> Outcome:
        """
        Remove a game's registry entry, library, and local profile.
        """

        try:
            RegistryService.delete_registry(game_id)

            SaveCloudLibrary.delete_game_library(game_id)

            device_id = SaveCloudLibrary.device_id()

            if DeviceService.exists(device_id, game_id):
                DeviceService.delete_profile(device_id, game_id)

        except Exception as error:
            return Outcome(ok=False, game_id=game_id, message=str(error))

        return Outcome(
            ok=True,
            message=f"Removed {game_id} from this device.",
        )

    # ------------------------------------------------------------------
    # Installation settings
    # ------------------------------------------------------------------

    @staticmethod
    def settings() -> Settings:
        """
        The installation's own configuration.
        """

        from savecloud.services.credentials import CredentialService

        config = ConfigurationService.load()

        backend = StorageRegistry.get(config.storage_backend)

        needs = bool(backend and backend.requires_setup())

        return Settings(
            backend=config.storage_backend,
            root=str(config.storage_root),
            retention=config.version_retention,
            needs_credentials=needs,
            has_credentials=(
                CredentialService.exists(config.storage_backend)
                if needs
                else True
            ),
        )

    @staticmethod
    def save_settings(
        backend: str,
        root: str,
        retention: int,
    ) -> Outcome:
        """
        Change where saves go and how much history is kept.

        Retention is applied rather than only recorded, matching what
        `config retention` does: a window that took effect at some
        unpredictable later moment would read as one that did nothing.
        """

        try:
            ConfigurationService.set_backend(backend)

            ConfigurationService.set_root(Path(root).expanduser())

            config = ConfigurationService.set_retention(int(retention))

        except Exception as error:
            return Outcome(ok=False, message=str(error))

        removed = SaveService.apply_retention(config.version_retention)

        lines = ["Settings saved."]

        if removed:
            trimmed = sum(len(versions) for versions in removed.values())

            lines.append(f"Removed {trimmed} versions beyond the window.")

        try:
            remote = SyncService.prune_remote(config.version_retention)

        except Exception:
            #
            # Storage catches up on the next upload. Failing to reach
            # it is not a reason to reject the setting.
            #
            remote = {}

            lines.append("Storage was not trimmed; it will be on next upload.")

        if remote:
            trimmed = sum(len(versions) for versions in remote.values())

            lines.append(f"Removed {trimmed} versions from storage.")

        return Outcome(ok=True, message="\n".join(lines))

    @staticmethod
    def dropbox_authorize_url(app_key: str) -> Outcome:
        """
        The URL that grants SaveCloud access to a Dropbox account.
        """

        from savecloud.storage.dropbox_setup import authorize_url

        if not app_key.strip():
            return Outcome(ok=False, message="App key is required.")

        return Outcome(ok=True, value=authorize_url(app_key.strip()))

    @staticmethod
    def save_dropbox_credentials(
        app_key: str,
        app_secret: str,
        code: str,
    ) -> Outcome:
        """
        Exchange an authorization code for a refresh token and store it.
        """

        from savecloud.services.credentials import CredentialService
        from savecloud.storage.dropbox import PROVIDER, DropboxStorageBackend
        from savecloud.storage.dropbox_setup import exchange_code

        missing = [
            label
            for label, value in (
                ("App key", app_key),
                ("App secret", app_secret),
                ("Authorization code", code),
            )
            if not value.strip()
        ]

        if missing:
            return Outcome(
                ok=False,
                message=f"{', '.join(missing)} required.",
            )

        try:
            response = exchange_code(
                app_key.strip(),
                app_secret.strip(),
                code.strip(),
            )

        except Exception as error:
            return Outcome(ok=False, message=str(error))

        refresh_token = response.get("refresh_token")

        if not refresh_token:
            return Outcome(
                ok=False,
                message=(
                    "Dropbox did not return a refresh token. The "
                    "authorization code may already have been used - "
                    "each one works once."
                ),
            )

        CredentialService.save(
            PROVIDER,
            {
                "app_key": app_key.strip(),
                "app_secret": app_secret.strip(),
                "refresh_token": refresh_token,
            },
        )

        #
        # The cached client holds the previous credentials.
        #

        DropboxStorageBackend.reset()

        return Outcome(ok=True, message="Dropbox is set up on this device.")


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
