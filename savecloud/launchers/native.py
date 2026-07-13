"""
Native process launcher.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess

from savecloud.launchers.base import BaseLauncher
from savecloud.launchers.registry import LauncherRegistry


class NativeLauncher(BaseLauncher):
    """
    Launches games directly using subprocess.
    """

    @staticmethod
    def display_name() -> str:
        return "Native"

    @staticmethod
    def validate(
        command: str,
    ) -> bool:
        """
        Validate a native launch command.
        """

        if not command.strip():
            return False

        executable = shlex.split(command)[0]

        return shutil.which(executable) is not None

    @staticmethod
    def launch(
        command: str,
    ) -> subprocess.Popen:
        """
        Launch a native process.
        """

        return subprocess.Popen(
            shlex.split(command),
        )


LauncherRegistry.register(
    "native",
    NativeLauncher,
)
