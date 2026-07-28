"""
Steam launcher.

Starts a game through Steam rather than executing it directly, so Steam
applies the compatibility tool, launch options, controller layout, and
overlay it is configured to use.

An important caveat: `steam -applaunch` returns as soon as Steam has
been told to start the game, not when the game exits. SaveCloud
therefore cannot tell when the session ended, and `savecloud play`
would capture the save immediately rather than afterwards.

For a game Steam launches, prefer `savecloud wrap` in the game's launch
options - there Steam runs SaveCloud, so the process tree is the right
way round and the exit is observable.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess

from savecloud.launchers.base import BaseLauncher
from savecloud.launchers.registry import LauncherRegistry


class SteamLauncher(BaseLauncher):
    """
    Launch a game through the Steam client.
    """

    @staticmethod
    def display_name() -> str:
        """
        Human-readable launcher name.
        """

        return "Steam"

    @staticmethod
    def tracks_process_exit() -> bool:
        """
        Steam detaches the game, so its exit cannot be observed.
        """

        return False

    @staticmethod
    def validate(
        command: str,
    ) -> bool:
        """
        Validate a Steam launch command.

        Accepts a bare App ID, which is what registration records.
        """

        command = command.strip()

        if not command:
            return False

        if shutil.which("steam") is None:
            return False

        if command.isdigit():
            return True

        #
        # Also accept a full command line, so an unusual install can
        # supply its own invocation.
        #

        parts = shlex.split(command)

        return bool(parts) and shutil.which(parts[0]) is not None

    @staticmethod
    def launch(
        command: str,
    ) -> subprocess.Popen:
        """
        Ask Steam to start a game.
        """

        command = command.strip()

        if command.isdigit():
            argv = ["steam", "-applaunch", command]

        else:
            argv = shlex.split(command)

        return subprocess.Popen(argv)


LauncherRegistry.register(
    "steam",
    SteamLauncher,
)
