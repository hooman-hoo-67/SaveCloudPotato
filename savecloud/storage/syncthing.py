"""
Syncthing storage backend.
"""

from __future__ import annotations

from savecloud.models.game import Game
from savecloud.storage.base import BaseStorageBackend
from savecloud.storage.registry import StorageRegistry


class SyncthingStorageBackend(
    BaseStorageBackend,
):
    """
    Syncthing storage backend.

    Placeholder implementation until Syncthing integration
    is implemented.
    """

    @staticmethod
    def display_name() -> str:
        """
        Return the backend display name.
        """

        return "Syncthing"

    @staticmethod
    def validate() -> bool:
        """
        Validate the backend configuration.
        """

        return False

    @staticmethod
    def available(
        game: Game,
    ) -> bool:
        """
        Return True if the backend is currently available.
        """

        return False

    @staticmethod
    def exists(
        game: Game,
    ) -> bool:
        """
        Return True if remote storage exists.
        """

        raise NotImplementedError

    @staticmethod
    def upload(
        game: Game,
    ) -> None:
        """
        Upload the managed save.
        """

        raise NotImplementedError

    @staticmethod
    def download(
        game: Game,
    ) -> None:
        """
        Download the managed save.
        """

        raise NotImplementedError

    @staticmethod
    def delete(
        game: Game,
    ) -> None:
        """
        Delete the remote save.
        """

        raise NotImplementedError

    @staticmethod
    def metadata(
        game: Game,
    ) -> dict:
        """
        Return metadata describing the remote save.
        """

        raise NotImplementedError


StorageRegistry.register(
    "syncthing",
    SyncthingStorageBackend,
)
