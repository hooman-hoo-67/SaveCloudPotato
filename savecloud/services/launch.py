"""
Launch service.

Responsible for launching games and monitoring their process
lifecycle.
"""

from __future__ import annotations

import shlex
import subprocess

from savecloud.models.device_profile import DeviceProfile


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

        command = shlex.split(
            profile.launch_command,
        )

        return subprocess.Popen(
            command,
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
