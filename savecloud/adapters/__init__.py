"""
SaveCloud adapter registry.
"""

from savecloud.adapters.eden import EdenAdapter

SUPPORTED_ADAPTERS = {
    "eden": EdenAdapter,
}


def get_adapter(name: str):
    """
    Return the adapter class for an adapter name.
    """

    return SUPPORTED_ADAPTERS.get(
        name.lower(),
    )


def adapter_exists(name: str) -> bool:
    """
    Return True if an adapter exists.
    """

    return (
        get_adapter(name)
        is not None
    )