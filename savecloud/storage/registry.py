"""
SaveCloud storage backend registry.
"""

from savecloud.storage.local import LocalStorageBackend

SUPPORTED_BACKENDS = {
    "local": LocalStorageBackend,
}


def get_backend(name: str):
    """
    Return the backend class for a backend name.
    """

    return SUPPORTED_BACKENDS.get(
        name.lower(),
    )


def backend_exists(name: str) -> bool:
    """
    Return True if a backend exists.
    """

    return get_backend(name) is not None
