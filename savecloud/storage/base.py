"""
Base storage backend interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from savecloud.models.game import Game


class BaseStorageBackend(ABC):
    """
    Base class for all SaveCloud storage backends.
    """

    @staticmethod
    @abstractmethod
    def display_name() -> str:
        """
        Return the human-readable backend name.
        """

    @staticmethod
    @abstractmethod
    def validate() -> bool:
        """
        Validate that the backend is correctly configured.
        """

    @staticmethod
    @abstractmethod
    def upload() -> None:
        """
        Upload the SaveCloud Library to the storage backend.
        """

    @staticmethod
    @abstractmethod
    def download() -> None:
        """
        Download the SaveCloud Library from the storage backend.
        """

    @staticmethod
    @abstractmethod
    def exists(
        game: Game,
    ) -> bool:
        """
        Return True if a remote save exists.
        """

    @staticmethod
    @abstractmethod
    def delete(
        game: Game,
    ) -> None:
        """
        Delete the remote save.
        """

    @staticmethod
    @abstractmethod
    def metadata(
        game: Game,
    ) -> dict:
        """
        Return metadata describing the remote save.
        """

    @staticmethod
    @abstractmethod
    def available(
        game: Game,
    ) -> bool:
        """
        Return True if the backend is currently available.
        """
        return True
