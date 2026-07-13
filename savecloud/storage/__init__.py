"""
Storage backend registry.
"""

from savecloud.storage.base import BaseStorageBackend
from savecloud.storage.local import LocalStorageBackend
from savecloud.storage.registry import StorageRegistry
from savecloud.storage.syncthing import SyncthingStorageBackend

__all__ = [
    "BaseStorageBackend",
    "LocalStorageBackend",
    "SyncthingStorageBackend",
    "StorageRegistry",
]
