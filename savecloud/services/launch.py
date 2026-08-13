"""
Launch service.

Responsible for launching games and monitoring their process
lifecycle.
"""

from __future__ import annotations

import subprocess

from savecloud.launchers import LauncherRegistry

from savecloud.models.device_profile import DeviceProfile
from savecloud.utils.executable import launch_options


class LaunchService:
    """
    Launch and monitor game processes.
    """

    @staticmethod
    def launch(
        profile: DeviceProfile,
    ) -> subprocess.Popen:
        """
        Launch a game.

        Parameters
        ----------
        profile
            Device profile containing the launch command.

        Returns
        -------
        subprocess.Popen
            Running process.
        """

        launcher = LauncherRegistry.get(
            profile.launcher,
        )

        if launcher is None:
            raise RuntimeError(
                f'Unknown launcher: "{profile.launcher}". '
                f"Available launchers: {', '.join(LauncherRegistry.names())}.",
            )

        if not profile.launch_command.strip():
            raise ValueError(
                f'"{profile.game_id}" has no launch command on this '
                f"device, so SaveCloud cannot start it. Either set one, "
                f"or launch it from Steam with:\n"
                f"    {launch_options(profile.game_id)}",
            )

        if not launcher.validate(
            profile.launch_command,
        ):
            raise ValueError(
                f"{launcher.display_name()} launcher cannot run this command: "
                f"{profile.launch_command}",
            )

        return launcher.launch(
            profile.launch_command,
        )

    @staticmethod
    def wait(
        process: subprocess.Popen,
    ) -> int:
        """
        Wait for a launched game to exit.

        Parameters
        ----------
        process
            Running process.

        Returns
        -------
        int
            Exit code.
        """

        return process.wait()

    @staticmethod
    def is_running(
        process: subprocess.Popen,
    ) -> bool:
        """
        Determine whether a process is still running.

        Parameters
        ----------
        process
            Running process.

        Returns
        -------
        bool
            True if the process is still running.
        """

        return process.poll() is None
