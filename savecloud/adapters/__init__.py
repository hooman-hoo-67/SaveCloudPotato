"""
SaveCloud adapter registry.
"""

from __future__ import annotations

from savecloud.adapters.base import BaseAdapter
from savecloud.adapters.eden import EdenAdapter
from savecloud.adapters.manual import ManualAdapter
from savecloud.adapters.steam_proton import SteamProtonAdapter


class AdapterRegistry:
    """
    Registry of all supported adapters.
    """

    _ADAPTERS: dict[str, type[BaseAdapter]] = {
        "eden": EdenAdapter,
        "manual": ManualAdapter,
        "steam-proton": SteamProtonAdapter,
    }

    @classmethod
    def get(
        cls,
        name: str,
    ) -> type[BaseAdapter] | None:
        """
        Return an adapter class.
        """

        return cls._ADAPTERS.get(
            name.lower(),
        )

    @classmethod
    def exists(
        cls,
        name: str,
    ) -> bool:
        """
        Return whether an adapter exists.
        """

        return cls.get(name) is not None

    @classmethod
    def names(
        cls,
    ) -> list[str]:
        """
        Return all adapter names.
        """

        return sorted(
            cls._ADAPTERS.keys(),
        )

    @classmethod
    def adapters(
        cls,
    ) -> dict[str, type[BaseAdapter]]:
        """
        Return the adapter mapping.
        """

        return dict(
            cls._ADAPTERS,
        )
