"""
Installation diagnostics.

Answers one question: is this installation in a state where a save
could be lost?

Every check is read-only and defensive. Diagnostics runs against
installations that are already broken, so it must never assume a file
parses, a directory exists, or a backend responds.
"""

from __future__ import annotations

from savecloud.adapters import AdapterRegistry
from savecloud.config.constants import library_dir
from savecloud.launchers import LauncherRegistry
from savecloud.models.diagnostic import Finding, Severity
from savecloud.models.game import SyncStatus
from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.storage import StorageRegistry
from savecloud.utils.executable import launch_options


class DiagnosticsService:
    """
    Inspect an installation and report what is wrong with it.
    """

    @staticmethod
    def run() -> list[Finding]:
        """
        Run every check.
        """

        findings: list[Finding] = []

        findings.extend(DiagnosticsService.check_installation())

        #
        # Everything below assumes the installation exists. If it does
        # not, further checks would only produce noise.
        #

        if any(finding.severity is Severity.ERROR for finding in findings):
            return findings

        findings.extend(DiagnosticsService.check_configuration())
        findings.extend(DiagnosticsService.check_games())
        findings.extend(DiagnosticsService.check_orphans())

        return findings

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    @staticmethod
    def check_installation() -> list[Finding]:
        """
        Verify the SaveCloud filesystem.
        """

        if not SaveCloudLibrary.exists():
            return [
                Finding(
                    severity=Severity.ERROR,
                    title="Installation",
                    detail="SaveCloud has not been initialized on this device.",
                    remedy="savecloud init",
                )
            ]

        if not SaveCloudLibrary.validate():
            return [
                Finding(
                    severity=Severity.ERROR,
                    title="Installation",
                    detail=(
                        "The installation is incomplete: a required "
                        "directory or the installation metadata is "
                        "missing or unreadable."
                    ),
                    remedy="savecloud init",
                )
            ]

        from savecloud.services import journal

        return [
            Finding(
                severity=Severity.OK,
                title="Installation",
                detail=(
                    f"{SaveCloudLibrary.device_name()} "
                    f"({SaveCloudLibrary.device_id()[:8]})\n"
                    f"Log: {journal.path()}"
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Configuration and storage
    # ------------------------------------------------------------------

    @staticmethod
    def check_configuration() -> list[Finding]:
        """
        Verify the configured storage backend.
        """

        findings: list[Finding] = []

        config = ConfigurationService.load()

        if not ConfigurationService.exists():
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Configuration",
                    detail=(
                        "config.json does not exist, so defaults are in "
                        "use. Nothing is broken, but the settings are "
                        "not recorded anywhere."
                    ),
                    remedy="savecloud init",
                )
            )

        backend = StorageRegistry.get(config.storage_backend)

        if backend is None:
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    title="Storage backend",
                    detail=(
                        f'"{config.storage_backend}" is not a registered '
                        f"backend, so nothing can be synchronized."
                    ),
                    remedy=(
                        f"savecloud config backend "
                        f"<{'|'.join(StorageRegistry.names())}>"
                    ),
                )
            )

            return findings

        if not backend.available():
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    title="Storage backend",
                    detail=backend.unavailable_reason(),
                    remedy=(
                        "Saves are still captured locally, but nothing "
                        "will reach your other devices until this is "
                        "fixed."
                    ),
                )
            )

            return findings

        findings.append(
            Finding(
                severity=Severity.OK,
                title="Storage backend",
                detail=f"{backend.display_name()} at {config.storage_root}",
            )
        )

        #
        # Ask the backend whether it has anything provider-specific to
        # report. Diagnostics deliberately does not know what that
        # might be.
        #

        try:
            warnings = backend.provider_warnings()

        except Exception as error:
            warnings = [f"Could not check provider state: {error}"]

        if warnings:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title=f"{backend.display_name()} provider",
                    detail="\n".join(warnings),
                    remedy=(
                        "Inspect these files and copy anything you want "
                        "to keep into a save directory, then delete "
                        "them. SaveCloud never reads them."
                    ),
                )
            )

        return findings

    # ------------------------------------------------------------------
    # Games
    # ------------------------------------------------------------------

    @staticmethod
    def check_games() -> list[Finding]:
        """
        Check every registered game.
        """

        findings: list[Finding] = []

        game_ids = RegistryService.list_game_ids()

        if not game_ids:
            findings.append(
                Finding(
                    severity=Severity.OK,
                    title="Games",
                    detail="No games are registered.",
                )
            )

            return findings

        for game_id in game_ids:
            findings.extend(DiagnosticsService.check_game(game_id))

        return findings

    @staticmethod
    def check_game(game_id: str) -> list[Finding]:
        """
        Check one registered game.
        """

        findings: list[Finding] = []

        #
        # Registry
        #

        try:
            game = RegistryService.load_game(game_id)

        except Exception as error:
            return [
                Finding(
                    severity=Severity.ERROR,
                    title="Registry unreadable",
                    detail=f"{error}",
                    remedy=(
                        f"Re-register the game, or restore its registry "
                        f"from another device with: savecloud pair {game_id}"
                    ),
                    game_id=game_id,
                )
            ]

        #
        # Library
        #

        if not SaveCloudLibrary.metadata_path(game_id).exists():
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    title="Library missing",
                    detail="The game is registered but has no library.",
                    remedy=f"savecloud sync {game_id}",
                    game_id=game_id,
                )
            )

        #
        # Adapter and launcher must still be registered. A save
        # configured against an adapter that no longer exists cannot be
        # located.
        #

        if not AdapterRegistry.exists(game.manifest.adapter):
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    title="Unknown adapter",
                    detail=(
                        f'The manifest names adapter '
                        f'"{game.manifest.adapter}", which is not registered.'
                    ),
                    remedy=f"Available: {', '.join(AdapterRegistry.names())}",
                    game_id=game_id,
                )
            )

        #
        # Device profile
        #

        device_id = SaveCloudLibrary.device_id()

        if not DeviceService.exists(device_id, game_id):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Not set up on this device",
                    detail=(
                        "The game is registered and synchronized but has "
                        "no profile here, so it cannot be played or "
                        "captured on this machine."
                    ),
                    remedy=f"savecloud pair {game_id}",
                    game_id=game_id,
                )
            )

        else:
            findings.extend(
                DiagnosticsService.check_profile(game_id, device_id),
            )

        #
        # Runtime state
        #

        findings.extend(DiagnosticsService.check_runtime(game))

        #
        # Report a clean game so the user sees it was checked.
        #

        if not any(finding.game_id == game_id for finding in findings):
            findings.append(
                Finding(
                    severity=Severity.OK,
                    title=game.manifest.display_name,
                    detail=f"{game_id}: healthy",
                    game_id=game_id,
                )
            )

        return findings

    @staticmethod
    def check_profile(
        game_id: str,
        device_id: str,
    ) -> list[Finding]:
        """
        Check this device's profile for a game.
        """

        findings: list[Finding] = []

        try:
            profile = DeviceService.load_profile(device_id, game_id)

        except Exception as error:
            return [
                Finding(
                    severity=Severity.ERROR,
                    title="Device profile unreadable",
                    detail=f"{error}",
                    remedy=f"savecloud pair {game_id}",
                    game_id=game_id,
                )
            ]

        #
        # Working save
        #

        if not profile.working_save_path.exists():
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Working save missing",
                    detail=(
                        f"{profile.working_save_path} does not exist. The "
                        f"game may not have run yet on this device, or "
                        f"the path may have changed."
                    ),
                    remedy=f"savecloud export {game_id}",
                    game_id=game_id,
                )
            )

        #
        # Launcher
        #

        launcher = LauncherRegistry.get(profile.launcher)

        if launcher is None:
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    title="Unknown launcher",
                    detail=(
                        f'The profile names launcher "{profile.launcher}", '
                        f"which is not registered."
                    ),
                    remedy=f"Available: {', '.join(LauncherRegistry.names())}",
                    game_id=game_id,
                )
            )

            return findings

        #
        # A launcher that hands off to a client cannot report the
        # game's exit, so `play` refuses it. That is expected rather
        # than broken, but the user needs to know how to launch it.
        #

        if not launcher.tracks_process_exit():
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title=f"Launch through {launcher.display_name()}",
                    detail=(
                        f"{launcher.display_name()} cannot report when the "
                        f"game exits, so `savecloud play` will refuse to "
                        f"start it and the save would never be captured."
                    ),
                    remedy=(
                        f"Put this in the game's launch options, then "
                        f"launch it from {launcher.display_name()}:\n"
                        f"{launch_options(game_id)}"
                    ),
                    game_id=game_id,
                )
            )

            return findings

        #
        # No launch command is a choice, not a fault. A game started
        # from Steam is started by Steam; SaveCloud only needs one to
        # run the game itself.
        #

        if not profile.launch_command.strip():
            findings.append(
                Finding(
                    severity=Severity.OK,
                    title="Launched through Steam",
                    #
                    # In the detail rather than the remedy: `doctor`
                    # prints a remedy only for problems, and this is
                    # not one - so a remedy here would never be shown.
                    #
                    detail=(
                        f"No launch command is set, so this game is "
                        f"started by Steam rather than by SaveCloud.\n"
                        f"Steam launch options:\n"
                        f"    {launch_options(game_id)}"
                    ),
                    game_id=game_id,
                )
            )

            return findings

        if not launcher.validate(profile.launch_command):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Launch command will not run",
                    detail=(
                        f"{launcher.display_name()} cannot run: "
                        f"{profile.launch_command}"
                    ),
                    remedy=(
                        "Synchronization still works; only `savecloud "
                        "play` is affected."
                    ),
                    game_id=game_id,
                )
            )

        return findings

    @staticmethod
    def check_runtime(game) -> list[Finding]:
        """
        Check a game's recorded runtime state.
        """

        findings: list[Finding] = []

        game_id = game.manifest.game_id

        runtime = game.runtime

        if runtime.status is SyncStatus.CONFLICT:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Unresolved conflict",
                    detail=(
                        "This device and storage both changed since the "
                        "last synchronization. Nothing has been "
                        "overwritten."
                    ),
                    remedy=(
                        f"savecloud sync {game_id} --keep-local\n"
                        f"savecloud sync {game_id} --keep-remote"
                    ),
                    game_id=game_id,
                )
            )

        elif runtime.status is SyncStatus.ERROR:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Last operation failed",
                    detail=runtime.last_error or "No detail was recorded.",
                    remedy=f"savecloud sync {game_id}",
                    game_id=game_id,
                )
            )

        elif runtime.pending_upload:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Save waiting to upload",
                    detail=(
                        "A session was captured locally but never reached "
                        "storage, so other devices cannot see it yet."
                    ),
                    remedy=f"savecloud sync {game_id}",
                    game_id=game_id,
                )
            )

        if runtime.status is SyncStatus.RUNNING:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Marked as running",
                    detail=(
                        "The game is recorded as still running. If it is "
                        "not, a previous session ended without SaveCloud "
                        "noticing and its save was never captured."
                    ),
                    remedy=f"savecloud sync {game_id}",
                    game_id=game_id,
                )
            )

        return findings

    # ------------------------------------------------------------------
    # Orphans
    # ------------------------------------------------------------------

    @staticmethod
    def check_orphans() -> list[Finding]:
        """
        Find data belonging to games that are no longer registered.
        """

        findings: list[Finding] = []

        registered = set(RegistryService.list_game_ids())

        #
        # Libraries without a registry entry. These hold real save
        # data, so they are worth reporting rather than ignoring.
        #

        libraries = library_dir()

        if libraries.exists():

            for directory in sorted(libraries.iterdir()):

                if not directory.is_dir():
                    continue

                if directory.name in registered:
                    continue

                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        title="Orphaned library",
                        detail=(
                            f'Save data exists for "{directory.name}" but '
                            f"the game is not registered."
                        ),
                        remedy=(
                            f"The saves are still in {directory}. Delete "
                            f"the directory if you no longer want them."
                        ),
                        game_id=directory.name,
                    )
                )

        #
        # Device profiles for games that no longer exist.
        #

        try:
            device_id = SaveCloudLibrary.device_id()

        except Exception:
            return findings

        for game_id in DeviceService.list_profiles(device_id):

            if game_id in registered:
                continue

            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    title="Orphaned device profile",
                    detail=(
                        f'This device has settings for "{game_id}", which '
                        f"is not registered."
                    ),
                    remedy=f"savecloud unregister {game_id}",
                    game_id=game_id,
                )
            )

        return findings
