"""
Base storage backend interface.

A storage backend synchronizes the canonical library. It never reads or
writes a game's working save folder, never launches games, and never
decides *when* synchronization happens - that is the SyncService's job.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from savecloud.models.game import Game
from savecloud.models.remote_state import RemoteState


class BaseStorageBackend(ABC):
    """
    Base class for all SaveCloud storage backends.
    """

    @staticmethod
    @abstractmethod
    def display_name() -> str:
        """
        Human-readable backend name.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        """
        Return True if this backend is usable right now.

        A backend that is configured but temporarily unreachable should
        return False rather than raising, so that SaveCloud can keep
        operating on the local library.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def unavailable_reason(cls) -> str:
        """
        Explain why the backend is unavailable.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def exists(
        cls,
        game_id: str,
    ) -> bool:
        """
        Return True if the backend holds a save for this game.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def upload(
        cls,
        game: Game,
    ) -> RemoteState:
        """
        Upload the canonical library entry for a game.

        Returns the state now held by the backend.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def download(
        cls,
        game_id: str,
    ) -> RemoteState:
        """
        Download a game's library entry from the backend.

        Returns the state that was downloaded.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def fetch_current(
        cls,
        game_id: str,
        destination,
    ) -> RemoteState:
        """
        Copy only the backend's current save to an arbitrary location.

        Unlike download(), this touches neither the library nor the
        registry. It exists so that callers can inspect or preserve the
        remote save without committing to it.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def delete(
        cls,
        game_id: str,
    ) -> None:
        """
        Remove a game from the backend.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def state(
        cls,
        game_id: str,
    ) -> RemoteState | None:
        """
        Return the backend's recorded state for a game.

        Returns None when the backend holds nothing for this game.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def list_games(cls) -> list[str]:
        """
        Return every game ID held by the backend.

        This is what makes pairing a new device possible.
        """

        raise NotImplementedError
