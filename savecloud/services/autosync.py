"""
Automatic synchronization service.

Responsible for orchestrating the complete game lifecycle:

    download
        ↓
    launch
        ↓
    wait
        ↓
    snapshot
        ↓
    upload
"""

from __future__ import annotations

from savecloud.models.game import Game
from savecloud.services.device import DeviceService
from savecloud.services.launch import LaunchService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService


class AutoSyncService:
    """
    High-level automatic synchronization workflows.
    """

    @staticmethod
    def play(
        game: Game,
    ) -> int:
        """
        Play a managed game.

        Workflow:

            1. Download the latest managed save.
            2. Launch the game.
            3. Wait for the game to exit.
            4. Upload the updated save if the game exited
               successfully.

        Parameters
        ----------
        game
            Registered game.

        Returns
        -------
        int
            Game process exit code.
        """

        profile = DeviceService.load_profile(
            SaveCloudLibrary.device_id(),
            game.manifest.game_id,
        )

        #
        # Always synchronize before launching.
        #

        SyncService.download(
            game,
        )

        #
        # Mark runtime as running.
        #

        game.runtime.mark_running()

        RegistryService.update_runtime(
            game,
        )

        #
        # Launch the game.
        #

        process = LaunchService.launch(
            profile,
        )

        #
        # Wait for the game to exit.
        #

        exit_code = LaunchService.wait(
            process,
        )

        #
        # Record exit information.
        #

        game.runtime.mark_exited(
            exit_code,
        )

        RegistryService.update_runtime(
            game,
        )

        #
        # Upload only after a successful exit.
        #

        if exit_code == 0:

            SyncService.upload(
                game,
            )

        else:

            game.runtime.mark_error(
                f"Game exited with code {exit_code}",
            )

            RegistryService.update_runtime(
                game,
            )

        return exit_code
