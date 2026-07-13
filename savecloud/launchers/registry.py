"""
SaveCloud launcher registry.
"""

from __future__ import annotations

from savecloud.launchers.base import BaseLauncher


class LauncherRegistry:
    """
    Registry of all supported launchers.
    """

    _LAUNCHERS: dict[str, type[BaseLauncher]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        launcher: type[BaseLauncher],
    ) -> None:
        """
        Register a launcher implementation.
        """

        cls._LAUNCHERS[name.lower()] = launcher

    @classmethod
    def get(
        cls,
        name: str,
    ) -> type[BaseLauncher] | None:
        """
        Return a launcher class.
        """

        return cls._LAUNCHERS.get(
            name.lower(),
        )

    @classmethod
    def exists(
        cls,
        name: str,
    ) -> bool:
        """
        Return whether a launcher exists.
        """

        return cls.get(name) is not None

    @classmethod
    def names(
        cls,
    ) -> list[str]:
        """
        Return registered launcher names.
        """

        return sorted(
            cls._LAUNCHERS.keys(),
        )

    @classmethod
    def launchers(
        cls,
    ) -> dict[str, type[BaseLauncher]]:
        """
        Return a copy of the launcher mapping.
        """

        return dict(
            cls._LAUNCHERS,
        )
