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
