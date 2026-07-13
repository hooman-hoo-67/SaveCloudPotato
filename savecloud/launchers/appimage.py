"""
AppImage launcher.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from savecloud.launchers.base import BaseLauncher
from savecloud.launchers.registry import LauncherRegistry


class AppImageLauncher(BaseLauncher):
    """
    Launch games distributed as AppImages.
    """

    @staticmethod
    def display_name() -> str:
        """
        Human-readable launcher name.
        """
        return "AppImage"

    @staticmethod
    def validate(
        command: str,
    ) -> bool:
        """
        Validate an AppImage launch command.
        """

        if not command.strip():
            return False

        executable = Path(
            shlex.split(command)[0],
        )

        return (
            executable.exists()
            and executable.is_file()
            and executable.suffix == ".AppImage"
        )

    @staticmethod
    def launch(
        command: str,
    ) -> subprocess.Popen:
        """
        Launch an AppImage.
        """

        return subprocess.Popen(
            shlex.split(command),
        )


LauncherRegistry.register(
    "appimage",
    AppImageLauncher,
)
