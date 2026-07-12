"""
Local storage backend.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from savecloud.models.game import Game
from savecloud.services.library import SaveCloudLibrary


class LocalStorageBackend:
    """
    Local folder storage backend.
    """

    @staticmethod
    def storage_root() -> Path:
        """
        Return the root directory for local storage.
        """

        return Path.home() / "SaveCloudRemote"

    @staticmethod
    def game_directory(
        game_id: str,
    ) -> Path:
        """
        Return the storage directory for a game.
        """

        return LocalStorageBackend.storage_root() / game_id

    @staticmethod
    def ensure_game_directory(
        game_id: str,
    ) -> Path:
        """
        Create the storage directory for a game if it
        does not already exist.
        """

        directory = LocalStorageBackend.game_directory(
            game_id,
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return directory

    @staticmethod
    def upload(
        game: Game,
    ) -> None:
        """
        Upload the managed save to local storage.
        """

        source = SaveCloudLibrary.current_directory(
            game.manifest.game_id,
        )

        if not source.exists():
            raise FileNotFoundError(f"Managed save directory does not exist: {source}")

        destination = (
            LocalStorageBackend.ensure_game_directory(
                game.manifest.game_id,
            )
            / "current"
        )

        if destination.exists():
            shutil.rmtree(destination)

        shutil.copytree(
            source,
            destination,
        )

    @staticmethod
    def download(
        game: Game,
    ) -> None:
        """
        Download the managed save from local storage.
        """

        source = (
            LocalStorageBackend.game_directory(
                game.manifest.game_id,
            )
            / "current"
        )

        if not source.exists():
            raise FileNotFoundError(f"Remote save directory does not exist: {source}")

        destination = SaveCloudLibrary.current_directory(
            game.manifest.game_id,
        )

        if destination.exists():
            shutil.rmtree(destination)

        shutil.copytree(
            source,
            destination,
        )
