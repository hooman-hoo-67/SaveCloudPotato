"""
Base adapter interface.

Every platform-specific adapter should inherit from this
class and implement its required methods.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from pathlib import Path


class BaseAdapter(ABC):
    """
    Base class for all SaveCloud adapters.
    """

    @staticmethod
    @abstractmethod
    def display_name() -> str:
        """
        Human-readable adapter name.
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def identifier_name() -> str:
        """
        Name of the identifier expected by this adapter.

        Examples:

            Title ID
            Steam App ID
            Game ID
            Save Folder
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def locate_save(
        identifier: str,
    ) -> Path | None:
        """
        Locate a save directory using the adapter's
        identifier.
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def validate_save(
        path: Path,
    ) -> bool:
        """
        Validate a discovered save directory.
        """

        raise NotImplementedError

    @staticmethod
    def identifier_is_path() -> bool:
        """
        Return whether the identifier is a filesystem path.

        A Title ID and a save folder are not the same question, and an
        interface that offers to browse for one of them when it wants
        the other sends people looking through their filesystem for a
        number.

        Defaults to False, so an adapter that says nothing gets a plain
        field rather than a misleading Browse button.
        """

        return False

    @staticmethod
    def supports_auto_discovery() -> bool:
        """
        Return whether this adapter can automatically
        locate saves.
        """

        return False
