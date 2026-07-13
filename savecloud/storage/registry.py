"""
SaveCloud storage backend registry.
"""

from __future__ import annotations

from typing import Type

from savecloud.storage.base import BaseStorageBackend
from savecloud.models.game import Game


class StorageRegistry:
    """
    Registry of available storage backends.
    """

    _backends: dict[
        str,
        Type[BaseStorageBackend],
    ] = {}

    @staticmethod
    def register(
        name: str,
        backend: Type[BaseStorageBackend],
    ) -> None:
        """
        Register a storage backend.
        """

        StorageRegistry._backends[name.lower()] = backend

    @staticmethod
    def get(
        name: str,
    ) -> Type[BaseStorageBackend] | None:
        """
        Return a storage backend.
        """

        return StorageRegistry._backends.get(
            name.lower(),
        )

    @staticmethod
    def exists(
        name: str,
    ) -> bool:
        """
        Return True if the backend exists.
        """

        return name.lower() in StorageRegistry._backends

    @staticmethod
    def names() -> list[str]:
        """
        Return registered backend names.
        """

        return sorted(
            StorageRegistry._backends.keys(),
        )

    @staticmethod
    def resolve(
        game: Game,
    ) -> type[BaseStorageBackend]:
        """
        Return the configured storage backend for a game.
        """

        backend = StorageRegistry.get(
            game.manifest.storage_backend,
        )

        assert backend is not None

        return backend
