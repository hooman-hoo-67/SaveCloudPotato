"""
Base launcher interface.

Every launcher implementation should inherit from this
class.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from subprocess import Popen


class BaseLauncher(ABC):
    """
    Base class for all SaveCloud launchers.
    """

    @staticmethod
    @abstractmethod
    def display_name() -> str:
        """
        Human-readable launcher name.
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def validate(
        command: str,
    ) -> bool:
        """
        Validate that a launch command is usable by
        this launcher.
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def launch(
        command: str,
    ) -> Popen:
        """
        Launch a game.

        Returns
        -------
        subprocess.Popen
            Running process.
        """

        raise NotImplementedError

    @staticmethod
    def tracks_process_exit() -> bool:
        """
        Return whether the launched process ends when the game does.

        A launcher that hands off to a client - Steam, and any store
        front like it - returns as soon as the request is delivered.
        Waiting on that process says nothing about the game, so
        capturing a save when it returns would record the state from
        *before* the session and mark it synchronized.

        Launchers in that position must return False, which is what
        stops `savecloud play` from using them.
        """

        return True
