"""
SaveCloud storage backend registry.

Services ask the registry for a backend rather than selecting one with
conditionals, so adding a provider never requires editing a service.
"""

from __future__ import annotations

from savecloud.storage.base import BaseStorageBackend
from savecloud.storage.dropbox import DropboxStorageBackend
from savecloud.storage.local import LocalStorageBackend
from savecloud.storage.syncthing import SyncthingStorageBackend


class StorageRegistry:
    """
    Registry of all supported storage backends.
    """

    _BACKENDS: dict[str, type[BaseStorageBackend]] = {
        "dropbox": DropboxStorageBackend,
        "local": LocalStorageBackend,
        "syncthing": SyncthingStorageBackend,
    }

    @classmethod
    def register(
        cls,
        name: str,
        backend: type[BaseStorageBackend],
    ) -> None:
        """
        Register a storage backend implementation.
        """

        cls._BACKENDS[name.lower()] = backend

    @classmethod
    def get(
        cls,
        name: str,
    ) -> type[BaseStorageBackend] | None:
        """
        Return a backend class by name.
        """

        return cls._BACKENDS.get(
            name.lower(),
        )

    @classmethod
    def exists(
        cls,
        name: str,
    ) -> bool:
        """
        Return whether a backend exists.
        """

        return cls.get(name) is not None

    @classmethod
    def names(cls) -> list[str]:
        """
        Return every registered backend name.
        """

        return sorted(
            cls._BACKENDS.keys(),
        )

    @classmethod
    def backends(cls) -> dict[str, type[BaseStorageBackend]]:
        """
        Return a copy of the backend mapping.
        """

        return dict(
            cls._BACKENDS,
        )

    @classmethod
    def resolve(cls) -> type[BaseStorageBackend]:
        """
        Return the backend selected by the installation configuration.

        Raises
        ------
        RuntimeError
            If the configured backend is not registered.
        """

        from savecloud.services.configuration import ConfigurationService

        name = ConfigurationService.load().storage_backend

        backend = cls.get(name)

        if backend is None:
            raise RuntimeError(
                f'Unknown storage backend: "{name}". '
                f"Available backends: {', '.join(cls.names())}.",
            )

        return backend


#
# Module-level helpers.
#


def get_backend(name: str):
    """
    Return the backend class for a backend name.
    """

    return StorageRegistry.get(name)


def backend_exists(name: str) -> bool:
    """
    Return True if a backend exists.
    """

    return StorageRegistry.exists(name)


SUPPORTED_BACKENDS = StorageRegistry.backends()
