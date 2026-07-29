"""
SaveCloud storage framework.
"""

from savecloud.storage.base import BaseStorageBackend
from savecloud.storage.dropbox import DropboxStorageBackend
from savecloud.storage.filesystem import FilesystemStorageBackend
from savecloud.storage.local import LocalStorageBackend
from savecloud.storage.registry import (
    SUPPORTED_BACKENDS,
    StorageRegistry,
    backend_exists,
    get_backend,
)
from savecloud.storage.syncthing import SyncthingStorageBackend

__all__ = (
    "BaseStorageBackend",
    "DropboxStorageBackend",
    "FilesystemStorageBackend",
    "LocalStorageBackend",
    "SUPPORTED_BACKENDS",
    "StorageRegistry",
    "SyncthingStorageBackend",
    "backend_exists",
    "get_backend",
)
